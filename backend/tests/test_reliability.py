import asyncio
import time
import psycopg
from pydantic import BaseModel

from app.actions.schemas import ActionProposal
from app.agent.agent import build_agent
from app.agent.schemas import AgentDecision
from app.auth.schemas import UserPrincipal
from app.db.agent import AgentRepositoryError
from app.db.database import init_db
from app.rag.repository import KnowledgeRepositoryError
from app.tools.base import Tool, ToolResultError


class EmptyKnowledge:
    def search(self, *_args, **_kwargs):
        return []


class DiagnosisProvider:
    async def decide(self, state, _tools):
        if not state.tool_calls:
            return AgentDecision(action="call_tool", tool_name="get_service_health",
                                 arguments={"service": "payments-api"}, service="payments-api")
        return AgentDecision(action="diagnose", service="payments-api",
                             diagnosis="The service appears healthy.")


class AlternateEvidenceProvider:
    async def decide(self, state, _tools):
        if not state.tool_calls:
            return AgentDecision(action="call_tool", tool_name="search_runbooks", arguments={"query": "payments"}, service="payments-api")
        if not any(call.tool == "get_service_health" for call in state.tool_calls):
            return AgentDecision(action="call_tool", tool_name="get_service_health",
                                 arguments={"service": "payments-api"}, service="payments-api")
        return AgentDecision(
            action="diagnose", service="payments-api", diagnosis="Service is healthy.",
            proposed_action=ActionProposal(action_type="generate_report", target="payments-api",
                                           reason="Summarize available evidence.", risk_level="LOW", status="proposed"),
        )


class EmptyMetricsProvider:
    async def decide(self, state, _tools):
        if not state.tool_calls:
            return AgentDecision(action="call_tool", tool_name="get_metrics",
                                 arguments={"service": "payments-api"}, service="payments-api")
        return AgentDecision(
            action="diagnose", service="payments-api", diagnosis="The service is healthy.",
            proposed_action=ActionProposal(action_type="generate_report", target="payments-api",
                                           reason="Summarize available evidence.", risk_level="LOW", status="proposed"),
        )


def make_agent(database_path, provider):
    init_db(database_path)
    agent = build_agent(database_path, provider)
    agent.knowledge_repository = EmptyKnowledge()
    return agent


def test_llm_timeout_is_retried_then_returns_explicit_failure(database_path):
    class TimeoutProvider:
        def __init__(self):
            self.calls = 0

        async def decide(self, *_args):
            self.calls += 1
            await asyncio.sleep(0.05)
            raise AssertionError("wait_for should have timed out")

    provider = TimeoutProvider()
    agent = make_agent(database_path, provider)
    agent.llm_timeout_seconds = 0.005

    state = asyncio.run(agent.investigate("Investigate payments", UserPrincipal(username="operator", role="operator")))

    assert provider.calls == 2
    assert state.status == "failed"
    assert state.failure_states[-1].category == "llm_timeout"
    assert state.failure_states[-1].attempts == 2
    assert "No diagnosis was produced" in state.diagnosis


def test_missing_model_diagnosis_is_not_reported_as_success(database_path):
    class EmptyDiagnosisProvider:
        async def decide(self, *_args):
            return AgentDecision(action="diagnose")

    state = asyncio.run(make_agent(database_path, EmptyDiagnosisProvider()).investigate("Investigate payments"))

    assert state.status == "failed"
    assert state.escalation_required
    assert any(failure.category == "malformed_model_response" for failure in state.failure_states)
    assert "did not provide a diagnosis" in state.diagnosis


def test_temporary_retrieval_database_error_retries_once(database_path):
    agent = make_agent(database_path, DiagnosisProvider())

    class FlakyKnowledge:
        calls = 0

        def search(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                try:
                    raise psycopg.OperationalError("temporary connection issue")
                except psycopg.OperationalError as exc:
                    raise KnowledgeRepositoryError from exc
            return [{"source": "runbook.md", "document": "runbook", "chunk": 1,
                     "similarity": 0.8, "content": "Restart only after approval."}]

    repository = FlakyKnowledge()
    agent.knowledge_repository = repository
    state = asyncio.run(agent.investigate("Investigate payments"))

    assert repository.calls == 2
    recovered = [failure for failure in state.failure_states if failure.category == "temporary_database_error"]
    assert recovered and recovered[0].resolved and recovered[0].attempts == 2
    assert state.retrieval_status == "ok"


def test_retrieval_timeout_is_explicit_and_escalates(database_path):
    agent = make_agent(database_path, DiagnosisProvider())
    agent.retrieval_timeout_seconds = 0.005

    class SlowKnowledge:
        def search(self, *_args, **_kwargs):
            time.sleep(0.05)
            return []

    agent.knowledge_repository = SlowKnowledge()
    state = asyncio.run(agent.investigate("Investigate payments"))

    assert state.retrieval_status == "failed"
    assert any(failure.category == "retrieval_timeout" for failure in state.failure_states)
    assert state.status == "failed" and state.escalation_required
    assert "relevant guidance may exist" in state.diagnosis


def test_empty_retrieval_is_explicit_and_never_means_no_guidance(database_path):
    agent = make_agent(database_path, DiagnosisProvider())
    state = asyncio.run(agent.investigate("Investigate payments"))

    assert state.retrieval_status == "empty"
    assert any(failure.category == "retrieval_empty" for failure in state.failure_states)
    assert "does not exist" in state.diagnosis


def test_empty_tool_data_is_not_reported_as_healthy(database_path, monkeypatch):
    from app.tools.schemas import MetricsToolResult

    agent = make_agent(database_path, EmptyMetricsProvider())
    monkeypatch.setattr(agent.tools["get_metrics"], "run",
                        lambda _args: MetricsToolResult(service="payments-api", metrics=[]))
    state = asyncio.run(agent.investigate("Check payment latency"))

    assert any("empty records" in warning for warning in state.warnings)
    assert "does not establish healthy state" in state.diagnosis
    assert "Unverified model output" in state.diagnosis
    assert state.proposed_action is None
    assert state.status == "failed" and state.escalation_required


def test_tool_timeout_retries_then_agent_uses_alternative_evidence(database_path, monkeypatch):
    agent = make_agent(database_path, AlternateEvidenceProvider())
    agent.tool_timeout_seconds = 0.005
    monkeypatch.setattr(agent.tools["search_runbooks"], "run", lambda _args: time.sleep(0.05))
    from app.tools.schemas import HealthToolResult
    monkeypatch.setattr(agent.tools["get_service_health"], "run", lambda _args: HealthToolResult(
        service_id=1, name="payments-api", environment="production", repository="ops/payments", state="degraded"
    ))

    state = asyncio.run(agent.investigate("Investigate payments"))

    assert len(state.tool_calls) == 3
    assert state.tool_calls[0].success is False and state.tool_calls[1].success is False
    assert state.tool_calls[0].result["category"] == "tool_timeout"
    assert state.tool_calls[1].result["category"] == "tool_timeout"
    assert state.tool_calls[2].tool == "get_service_health" and state.tool_calls[2].success
    assert state.status == "failed"
    assert state.escalation_required
    assert "tool_timeout" in state.diagnosis
    assert state.proposed_action is None
    assert "not evidence of health" in state.diagnosis


def test_malformed_tool_result_is_structured_and_action_is_withheld(database_path, monkeypatch):
    agent = make_agent(database_path, AlternateEvidenceProvider())
    monkeypatch.setattr(agent.tools["search_runbooks"], "run",
                        lambda _args: (_ for _ in ()).throw(ToolResultError("bad schema")))

    state = asyncio.run(agent.investigate("Investigate payments"))

    assert state.tool_calls[0].success is False
    assert state.tool_calls[0].result["category"] == "malformed_tool_result"
    assert any(failure.category == "malformed_tool_result" for failure in state.failure_states)
    assert state.tool_calls[1].tool == "get_service_health" and state.tool_calls[1].success
    assert state.proposed_action is None
    assert "malformed_tool_result" in state.diagnosis
    assert state.status == "failed" and state.escalation_required


def test_run_creation_database_failure_returns_explicit_state(database_path, monkeypatch):
    agent = make_agent(database_path, DiagnosisProvider())

    def fail_create(*_args, **_kwargs):
        try:
            raise psycopg.OperationalError("database unavailable")
        except psycopg.OperationalError as exc:
            raise AgentRepositoryError from exc

    monkeypatch.setattr(agent.repository, "create_run", fail_create)
    state = asyncio.run(agent.investigate("Investigate payments"))

    assert state.status == "failed"
    assert state.failure_states[0].category == "temporary_database_error"
    assert "database persistence failed" in state.diagnosis


class BrokenOutput(BaseModel):
    required: str


class MalformedTool(Tool[dict, BrokenOutput]):
    name = "malformed"
    description = "Returns invalid structured data."
    input_schema = BrokenOutput
    result_schema = BrokenOutput

    def execute(self, _parameters):
        return {"wrong": True}


def test_tool_framework_distinguishes_malformed_result():
    try:
        MalformedTool().run({"required": "valid input"})
    except ToolResultError as exc:
        assert "malformed structured data" in str(exc)
    else:
        raise AssertionError("malformed result should be an explicit tool error")
