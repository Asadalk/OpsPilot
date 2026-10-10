"""Minimal Groq chat client for JSON-schema validated output.

Groq exposes an OpenAI-compatible HTTP API, so a direct httpx call is enough; no SDK
is added. The caller supplies a strict JSON schema and validates the parsed result.
"""
import json
from typing import Any

import httpx

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqError(Exception):
    """A Groq request failed. `status_code` lets the shared retry rules classify it."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after: float | None = None


def _retry_after_seconds(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


async def chat_json(
    *,
    api_key: str,
    model: str,
    prompt: str,
    schema: dict[str, Any],
    schema_name: str,
    timeout_seconds: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[Any, dict[str, int | None]]:
    """Return (parsed JSON, token usage) for one schema-constrained completion."""
    if not api_key.strip():
        raise GroqError("GROQ_API_KEY is missing in backend/.env")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        # gpt-oss models emit hidden reasoning tokens; "low" keeps each step within free-tier TPM.
        **({"reasoning_effort": "low"} if model.startswith("openai/gpt-oss") else {}),
        "response_format": {
            "type": "json_schema",
            # Non-strict: Groq still validates the output, but optional fields stay optional.
            # (Strict mode requires every property to be listed as required.)
            "json_schema": {"name": schema_name, "strict": False, "schema": schema},
        },
    }
    async with httpx.AsyncClient(timeout=timeout_seconds, transport=transport) as client:
        try:
            response = await client.post(GROQ_CHAT_URL, json=payload,
                                         headers={"Authorization": f"Bearer {api_key}"})
        except httpx.TimeoutException as exc:
            raise TimeoutError("Groq request timed out") from exc
        except httpx.TransportError as exc:
            raise ConnectionError(f"Groq request could not be sent: {type(exc).__name__}") from exc
    if response.status_code != 200:
        # Error bodies describe the request problem; they never echo the key.
        error = GroqError(f"Groq HTTP {response.status_code}: {response.text[:300]}", response.status_code)
        error.retry_after = _retry_after_seconds(response.headers.get("retry-after"))
        raise error
    body = response.json()
    usage = body.get("usage") or {}
    content = body["choices"][0]["message"]["content"]
    return json.loads(content), {
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
