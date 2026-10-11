"""Phase 30: the agent depends only on the DecisionProvider interface.

The same orchestration test runs against the offline mock provider and, when
LIVE_GROQ_API_KEY is set, against the real Groq provider.
"""
import asyncio
import dataclasses
import inspect
import os

import pytest

import app.agent.agent as agent_module
from app.agent.agent import build_agent
from app.agent.scripted import MockDecisionProvider
from app.auth.schemas import UserPrincipal
from app.db.database import get_connection, init_db

SERVICE = "mockpool-api"


def seed_pool_exhaustion(database_path):
    init_db(database_path)
    with get_connection(database_path) as connection:
        service_id = connection.execute(
            "INSERT INTO services (name, environment, repository, current_state, fault) "
            "VALUES (%s, 'production', 'example/mockpool-api', 'degraded', 'connection_pool_exhaustion') "
            "ON CONFLICT (name) DO UPDATE SET current_state = 'degraded', fault = 'connection_pool_exhaustion' "
            "RETURNING id", (SERVICE,),
        ).fetchone()["id"]
        connection.execute("INSERT INTO metrics (timestamp, service_id, metric_name, value) "
                           "VALUES (NOW(), %s, 'http_request_latency_ms', 1500)", (service_id,))
        connection.execute("INSERT INTO logs (timestamp, service_id, level, message, trace_id) VALUES "
                           "(NOW(), %s, 'error', 'DB_TIMEOUT acquiring connection from pool (active=50/50)', 'trace-mock')",
                           (service_id,))


def investigate(database_path, provider, timeout=None):
    agent = build_agent(database_path, provider)
    if timeout is not None:
        agent.llm_timeout_seconds = timeout
    return asyncio.run(agent.investigate(f"{SERVICE} latency is high. Investigate and fix it.",
                                         UserPrincipal(username="operator", role="operator")))


def assert_full_investigation(state):
    assert state.status == "paused"  # HIGH-risk production restart needs approval
    assert {call.tool for call in state.tool_calls} >= {"get_metrics", "search_logs"}
    assert all(call.arguments.get("service") == SERVICE for call in state.tool_calls if "service" in call.arguments)
    assert state.proposed_action.action_type == "restart_service"
    assert state.policy_decision.outcome == "require_approval"


def test_agent_module_does_not_reference_concrete_providers():
    source = inspect.getsource(agent_module)
    assert not any(name in source for name in ("Groq", "Gemini", "genai", "httpx"))


def test_mock_provider_drives_the_full_orchestration(database_path):
    seed_pool_exhaustion(database_path)
    assert_full_investigation(investigate(database_path, MockDecisionProvider()))


@pytest.mark.parametrize("mode, category, attempts", [
    ("timeout", "llm_timeout", 2),          # transient: retried once
    ("unavailable", "llm_failure", 2),      # transient: retried once
    ("malformed", "malformed_model_response", 1),  # not transient: no retry
])
def test_mock_failure_modes_end_in_explicit_failure(database_path, mode, category, attempts):
    seed_pool_exhaustion(database_path)
    state = investigate(database_path, MockDecisionProvider(mode), timeout=0.05)
    assert state.status == "failed"
    assert state.failure_states[-1].category == category
    assert state.failure_states[-1].attempts == attempts
    assert state.proposed_action is None and not state.tool_calls


def test_factory_selects_the_mock_provider(monkeypatch):
    import app.agent.provider as provider_module

    monkeypatch.setattr(provider_module, "settings",
                        dataclasses.replace(provider_module.settings, llm_provider="mock", mock_llm_mode="malformed"))
    provider = provider_module.build_decision_provider()
    assert isinstance(provider, MockDecisionProvider) and provider.mode == "malformed"


@pytest.mark.skipif(not os.getenv("LIVE_GROQ_API_KEY"), reason="live provider test; set LIVE_GROQ_API_KEY to run")
def test_groq_provider_drives_the_same_orchestration(database_path, monkeypatch):
    import app.agent.provider as provider_module

    monkeypatch.setattr(provider_module, "settings",
                        dataclasses.replace(provider_module.settings, groq_api_key=os.environ["LIVE_GROQ_API_KEY"],
                                            groq_tokens_per_minute=0))
    seed_pool_exhaustion(database_path)
    state = investigate(database_path, provider_module.GroqDecisionProvider())
    assert state.tool_calls and state.status in {"paused", "completed"}
    assert all(call.arguments.get("service") == SERVICE for call in state.tool_calls if "service" in call.arguments)
