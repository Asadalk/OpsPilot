"""Minimal Groq chat client for JSON-schema validated output.

Groq exposes an OpenAI-compatible HTTP API, so a direct httpx call is enough; no SDK
is added. The caller supplies a strict JSON schema and validates the parsed result.
"""
import asyncio
import json
import time
from collections import deque
from typing import Any

import httpx

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


# Tokens spent per call in the last minute: [monotonic start, tokens]. Waiting here
# before a call keeps us under the account's tokens-per-minute limit instead of
# collecting 429s. One process, sequential calls; concurrent callers may still race.
_RECENT_CALLS: deque[list[float]] = deque()


async def _wait_for_token_budget(estimate: int, tokens_per_minute: int) -> list[float]:
    while True:
        now = time.monotonic()
        while _RECENT_CALLS and now - _RECENT_CALLS[0][0] >= 60:
            _RECENT_CALLS.popleft()
        used = sum(tokens for _, tokens in _RECENT_CALLS)
        if tokens_per_minute <= 0 or not _RECENT_CALLS or used + estimate <= tokens_per_minute:
            entry = [now, float(estimate)]
            _RECENT_CALLS.append(entry)
            return entry
        await asyncio.sleep(60 - (now - _RECENT_CALLS[0][0]) + 0.1)


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
    tokens_per_minute: int = 0,
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
    # Rough estimate (4 characters per token plus room for output); replaced by actual usage below.
    budget = await _wait_for_token_budget(len(prompt) // 4 + 800, tokens_per_minute)
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
    budget[1] = float(usage.get("total_tokens") or budget[1])
    content = body["choices"][0]["message"]["content"]
    return json.loads(content), {
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
