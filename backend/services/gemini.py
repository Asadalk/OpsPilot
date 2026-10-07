"""Gemini task extraction using the official Google GenAI SDK."""
import json
import os
from typing import Any

from models import ExtractedTask
from services.rag import GuidelineChunk, build_context

DEFAULT_MODEL = "gemini-3.8-flash"
MODEL_PREFERENCES = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"]
RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "task": {"type": "STRING"},
            "owner": {"type": "STRING"},
            "deadline": {"type": "STRING"},
            "priority": {"type": "STRING", "enum": ["high", "medium", "low"]},
        },
        "required": ["task", "owner", "deadline", "priority"],
    },
}


class GeminiError(Exception):
    """An upstream Gemini failure suitable for returning as a 502."""


class GeminiTimeout(GeminiError):
    """Gemini did not respond before the configured timeout."""


def _client() -> Any:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiError("GEMINI_API_KEY is missing in backend/.env")
    try:
        timeout_ms = max(1000, int(os.getenv("GEMINI_TIMEOUT_SECONDS", "25")) * 1000)
    except ValueError:
        timeout_ms = 25_000
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise GeminiError("Google GenAI SDK is not installed; install backend requirements") from exc
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))


def _config() -> dict[str, Any]:
    # The SDK accepts GenerateContentConfig fields as a dictionary.
    return {
        "response_mime_type": "application/json",
        "response_schema": RESPONSE_SCHEMA,
    }


def _parse_tasks(raw: str) -> list[dict[str, Any]]:
    if not raw or not raw.strip():
        raise ValueError("Gemini returned an empty response")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Gemini response must be a JSON array")
    # Validate the entire array before returning any tasks for persistence.
    return [ExtractedTask.model_validate(item).model_dump() for item in data]


async def extract_tasks(
    text: str,
    client: Any = None,
    retrieved_guidelines: list[GuidelineChunk] | None = None,
) -> list[dict[str, Any]]:
    """Ask Gemini for schema-constrained JSON, retrying malformed output once."""
    active_client = client or _client()
    prompt = (
        "Extract actionable tasks from the supplied operational text. "
        "Use owner 'Unknown' and deadline 'Not specified' when absent. "
        "Do not invent details. Return an empty array if no actionable tasks exist.\n\n"
        f"OPERATIONAL INPUT:\n{text}\n\n"
        "RELEVANT OPERATIONAL GUIDELINES:\n"
        f"{build_context(retrieved_guidelines or [])}\n\n"
        "INSTRUCTIONS:\n"
        "Use the retrieved guidelines as domain context when determining priority, "
        "ownership, escalation, deadlines, and verification steps. Return only tasks "
        "supported by the operational input; do not invent details."
    )
    api_error: Exception | None = None
    for model in MODEL_PREFERENCES:
        for attempt in range(2):
            try:
                response = await active_client.aio.models.generate_content(
                    model=model,
                    contents=(prompt if attempt == 0 else prompt + "\nReturn only valid JSON matching the required schema."),
                    config=_config(),
                )
            except Exception as exc:
                api_error = exc
                break  # Try the next preferred Flash model.
            try:
                return _parse_tasks(response.text or "")
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                if attempt == 1:
                    raise GeminiError("Gemini returned invalid task data: " + str(exc)) from exc
    if api_error and "timeout" in (type(api_error).__name__ + str(api_error)).lower():
        raise GeminiTimeout("Gemini request timed out. Please try again.") from api_error
    if api_error and getattr(api_error, "status_code", None) in {429, 503}:
        raise GeminiError("Gemini is temporarily busy or rate limited. Please try again shortly.") from api_error
    raise GeminiError("Gemini request failed. Please try again.") from api_error
