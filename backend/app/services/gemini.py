"""Gemini task extraction using the official Google GenAI SDK."""
import json
from typing import Any

from app.core.config import settings
from app.models.schemas import ExtractedTask
from app.services.rag import GuidelineChunk, build_context

DEFAULT_MODEL = "gemini-2.5-flash"
MODEL_PREFERENCES = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.8-flash"]
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
    pass


class GeminiTimeout(GeminiError):
    pass


def _client() -> Any:
    if not settings.gemini_api_key.strip():
        raise GeminiError("GEMINI_API_KEY is missing in backend/.env")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise GeminiError("Google GenAI SDK is not installed; install backend requirements") from exc
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
    )


def _config() -> dict[str, Any]:
    return {"response_mime_type": "application/json", "response_schema": RESPONSE_SCHEMA}


def _model_preferences() -> list[str]:
    primary = settings.gemini_model.strip() or DEFAULT_MODEL
    configured = settings.gemini_fallback_models.split(",")
    fallbacks = configured if any(model.strip() for model in configured) else MODEL_PREFERENCES
    return list(dict.fromkeys([primary, *(model.strip() for model in fallbacks if model.strip())]))


def _parse_tasks(raw: str) -> list[dict[str, Any]]:
    if not raw or not raw.strip():
        raise ValueError("Gemini returned an empty response")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Gemini response must be a JSON array")
    return [ExtractedTask.model_validate(item).model_dump() for item in data]


async def extract_tasks(
    text: str,
    client: Any = None,
    retrieved_guidelines: list[GuidelineChunk] | None = None,
) -> list[dict[str, Any]]:
    active_client = client or _client()
    prompt = (
        "Extract actionable tasks from the supplied operational text. Use owner 'Unknown' and deadline "
        "'Not specified' when absent. Do not invent details. Return an empty array if no actionable tasks exist.\n\n"
        f"OPERATIONAL INPUT:\n{text}\n\nRELEVANT OPERATIONAL GUIDELINES:\n"
        f"{build_context(retrieved_guidelines or [])}\n\nINSTRUCTIONS:\n"
        "Use the retrieved guidelines as domain context when determining priority, ownership, escalation, "
        "deadlines, and verification steps. Return only tasks supported by the operational input; do not invent details."
    )
    api_error: Exception | None = None
    for model in _model_preferences():
        for attempt in range(2):
            try:
                response = await active_client.aio.models.generate_content(
                    model=model,
                    contents=(prompt if attempt == 0 else prompt + "\nReturn only valid JSON matching the required schema."),
                    config=_config(),
                )
            except Exception as exc:
                error_text = str(exc).lower()
                if "api key" in error_text and ("400" in error_text or "invalid" in error_text):
                    raise GeminiError("Gemini API key is invalid. Update GEMINI_API_KEY in backend/.env.") from exc
                api_error = exc
                break
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