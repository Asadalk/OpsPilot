import asyncio
import dataclasses
import json
from uuid import uuid4

import httpx
import pytest

from app.agent.schemas import AgentState
from app.llm.groq import GroqError, chat_json


def _transport(status: int, body: dict, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(status, json=body)
    return httpx.MockTransport(handler)


def test_chat_json_sends_schema_and_returns_usage():
    seen = []
    body = {"choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14}}
    data, usage = asyncio.run(chat_json(api_key="k", model="m", prompt="p", schema={"type": "object"},
                                        schema_name="s", timeout_seconds=5, transport=_transport(200, body, seen)))
    assert data == {"ok": True}
    assert usage == {"input_tokens": 11, "output_tokens": 3, "total_tokens": 14}
    assert seen[0]["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert seen[0]["temperature"] == 0


def test_chat_json_rate_limit_is_classified_as_transient():
    from app.reliability import is_transient_error

    with pytest.raises(GroqError) as raised:
        asyncio.run(chat_json(api_key="k", model="m", prompt="p", schema={}, schema_name="s", timeout_seconds=5,
                              transport=_transport(429, {"error": {"message": "rate limited"}}, [])))
    assert raised.value.status_code == 429
    assert is_transient_error(raised.value)


def test_groq_decision_provider_validates_and_strips_null_arguments(monkeypatch):
    import app.llm.groq as groq_module
    from app.agent.provider import GroqDecisionProvider

    async def fake_chat_json(**kwargs):
        assert kwargs["schema_name"] == "agent_decision"
        return ({"action": "call_tool", "tool_name": "get_metrics", "service": None, "severity": None,
                 "arguments": {"service": "payments-api", "limit": None, "metric_name": None, "query": None,
                               "level": None, "mode": None},
                 "hypotheses": [], "diagnosis": None, "proposed_action": None},
                {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7})

    monkeypatch.setattr(groq_module, "chat_json", fake_chat_json)
    provider = GroqDecisionProvider("test-model")
    decision = asyncio.run(provider.decide(AgentState(run_id=uuid4(), user_request="Why is payments-api slow?"), []))
    assert decision.arguments == {"service": "payments-api"}
    assert provider.last_usage["total_tokens"] == 7


def test_groq_decision_schema_rejects_extra_keys_and_covers_every_read_tool_argument():
    from app.agent.provider import GROQ_DECISION_SCHEMA
    from app.tools.registry import build_default_tools

    def check(node):
        if isinstance(node, dict):
            if "properties" in node:
                assert node["additionalProperties"] is False
                assert set(node["required"]) <= set(node["properties"])
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(GROQ_DECISION_SCHEMA)
    declared = set(GROQ_DECISION_SCHEMA["properties"]["arguments"]["properties"])
    for tool in build_default_tools("postgresql://unused").values():
        if tool.kind == "read":
            assert set(tool.input_schema.model_fields) <= declared, tool.name


def test_task_extraction_uses_groq_when_configured(monkeypatch):
    import app.llm.groq as groq_module
    from app.services import gemini

    async def fake_chat_json(**kwargs):
        assert kwargs["schema_name"] == "extracted_tasks"
        return {"tasks": [{"task": "Rotate key", "owner": "Asha", "deadline": "Friday", "priority": "high"}]}, {}

    monkeypatch.setattr(gemini, "settings", dataclasses.replace(gemini.settings, llm_provider="groq", groq_api_key="k"))
    monkeypatch.setattr(groq_module, "chat_json", fake_chat_json)
    assert asyncio.run(gemini.extract_tasks("Asha rotates the key by Friday")) == [
        {"task": "Rotate key", "owner": "Asha", "deadline": "Friday", "priority": "high"}]


def test_task_extraction_reports_missing_groq_key(monkeypatch):
    from app.services import gemini

    monkeypatch.setattr(gemini, "settings", dataclasses.replace(gemini.settings, llm_provider="groq", groq_api_key=""))
    with pytest.raises(gemini.GeminiError, match="GROQ_API_KEY"):
        asyncio.run(gemini.extract_tasks("Do it"))


def test_rate_limit_retry_waits_for_capped_retry_after(monkeypatch):
    import app.reliability as reliability

    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(reliability.asyncio, "sleep", fake_sleep)
    error = GroqError("rate limited", 429)
    error.retry_after = 7.5
    asyncio.run(reliability.backoff(1, error))
    error.retry_after = 600
    asyncio.run(reliability.backoff(1, error))
    asyncio.run(reliability.backoff(2, RuntimeError("no hint")))
    assert waits == [7.5, reliability.MAX_RETRY_AFTER_SECONDS, reliability.RETRY_BACKOFF_SECONDS * 2]


def test_chat_json_exposes_retry_after_header():
    def handler(request):
        return httpx.Response(429, headers={"retry-after": "4"}, json={"error": {}})

    with pytest.raises(GroqError) as raised:
        asyncio.run(chat_json(api_key="k", model="m", prompt="p", schema={}, schema_name="s", timeout_seconds=5,
                              transport=httpx.MockTransport(handler)))
    assert raised.value.retry_after == 4.0


def test_diagnose_decision_may_omit_arguments_and_schema_rejection_is_malformed(monkeypatch):
    import app.llm.groq as groq_module
    from app.agent.provider import GroqDecisionProvider, MalformedDecisionError

    async def diagnose(**_):
        return ({"action": "diagnose", "tool_name": None, "arguments": None, "service": "payments-api",
                 "severity": None, "hypotheses": [], "diagnosis": "Pool exhausted.", "proposed_action": None}, {})

    monkeypatch.setattr(groq_module, "chat_json", diagnose)
    state = AgentState(run_id=uuid4(), user_request="Why is payments-api slow?")
    decision = asyncio.run(GroqDecisionProvider("m").decide(state, []))
    assert decision.action == "diagnose" and decision.arguments == {}

    async def rejected(**_):
        raise GroqError("Groq HTTP 400: Generated JSON does not match the expected schema.", 400)

    monkeypatch.setattr(groq_module, "chat_json", rejected)
    with pytest.raises(MalformedDecisionError):
        asyncio.run(GroqDecisionProvider("m").decide(state, []))


def test_parse_decision_treats_null_lists_as_empty_but_rejects_null_required_fields():
    from app.agent.provider import MalformedDecisionError, parse_decision

    decision = parse_decision({"action": "call_tool", "tool_name": "get_metrics", "arguments": {"service": "x"},
                               "hypotheses": None, "diagnosis": None, "proposed_action": None})
    assert decision.hypotheses == []
    with pytest.raises(MalformedDecisionError):
        parse_decision({"action": "diagnose", "hypotheses": [{"hypothesis": None, "score": 0.5}]})


def test_groq_schema_limits_tool_name_to_advertised_read_tools():
    from app.agent.provider import groq_decision_schema

    schema = groq_decision_schema(["get_metrics", "search_logs"])
    call, diagnose = schema["anyOf"]
    assert call["properties"]["tool_name"]["enum"] == ["get_metrics", "search_logs"]
    assert set(call["required"]) == {"action", "tool_name", "arguments"}
    assert set(diagnose["required"]) == {"action", "diagnosis"}


def test_token_budget_waits_until_the_minute_window_has_room(monkeypatch):
    import app.llm.groq as groq_module

    clock = {"now": 1000.0}
    waits = []

    async def fake_sleep(seconds):
        waits.append(round(seconds, 1))
        clock["now"] += seconds

    monkeypatch.setattr(groq_module.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(groq_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(groq_module, "_RECENT_CALLS", groq_module.deque())

    asyncio.run(groq_module._wait_for_token_budget(5000, 8000))
    clock["now"] += 10
    asyncio.run(groq_module._wait_for_token_budget(5000, 8000))  # 10000 > 8000: waits for the first to age out
    assert waits == [50.1]
    asyncio.run(groq_module._wait_for_token_budget(5000, 0))  # pacing disabled
    assert waits == [50.1]
