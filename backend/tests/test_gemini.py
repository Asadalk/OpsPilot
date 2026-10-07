import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.gemini import GeminiError, GeminiTimeout, extract_tasks
from services.rag import retrieve


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)

        async def generate_content(**kwargs):
            response = next(self.responses)
            if isinstance(response, Exception):
                raise response
            return response

        models = SimpleNamespace(generate_content=AsyncMock(side_effect=generate_content))
        self.aio = SimpleNamespace(models=models)


def result(text):
    return SimpleNamespace(text=text)


def test_valid_model_response():
    client = FakeClient([result('[{"task":"Ship release","owner":"Jo","deadline":"Friday","priority":"high"}]')])
    retrieved = retrieve("Production deployment verification")
    tasks = asyncio.run(extract_tasks("Ship release Friday", client, retrieved))
    assert tasks[0]["task"] == "Ship release"
    call = client.aio.models.generate_content.call_args.kwargs
    assert call["config"]["response_mime_type"] == "application/json"
    assert "RELEVANT OPERATIONAL GUIDELINES" in call["contents"]
    assert "post-deployment verification" in call["contents"]


def test_malformed_response_retries_once():
    client = FakeClient([result("not json"), result("[]")])
    assert asyncio.run(extract_tasks("Do it", client)) == []
    assert client.aio.models.generate_content.call_count == 2


@pytest.mark.parametrize("text", [None, ""])
def test_empty_response_retries_then_fails(text):
    client = FakeClient([result(text), result(text)])
    with pytest.raises(GeminiError, match="invalid task data"):
        asyncio.run(extract_tasks("Do it", client))


def test_api_failure_tries_fallback_models_then_fails():
    client = FakeClient([RuntimeError("offline"), RuntimeError("offline"), RuntimeError("offline")])
    with pytest.raises(GeminiError, match="request failed"):
        asyncio.run(extract_tasks("Do it", client))
    assert client.aio.models.generate_content.call_count == 3


def test_timeout_is_classified():
    client = FakeClient([TimeoutError("request timeout"), TimeoutError("request timeout"), TimeoutError("request timeout")])
    with pytest.raises(GeminiTimeout, match="timed out"):
        asyncio.run(extract_tasks("Do it", client))


def test_missing_key_fails_without_import_crash(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(GeminiError, match="GEMINI_API_KEY"):
        asyncio.run(extract_tasks("Do it"))
