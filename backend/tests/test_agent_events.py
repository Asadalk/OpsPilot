import asyncio
from pathlib import Path
from uuid import uuid4

from app.actions.schemas import ActionProposal
from app.agent.agent import build_agent
from app.agent.events import AgentRunTrace
from app.agent.schemas import AgentDecision
from app.auth.schemas import UserPrincipal
from app.auth.service import AuthService
from app.db.agent_events import AgentEventRepository
from app.db.database import get_connection, init_db
from app.main import ops_agent
from app.rag.ingest import ingest_directory


class TraceProvider:
    model = "test-trace-model"

    def __init__(self, service="payments-api"):
        self.service = service

    async def decide(self, state, _tools):
        tools = ["get_metrics", "search_logs", "get_recent_deployments"]
        if len(state.tool_calls) < len(tools):
            name = tools[len(state.tool_calls)]
            return AgentDecision(action="call_tool", tool_name=name,
                                 arguments={"service": self.service}, service=self.service)
        return AgentDecision(
            action="diagnose", service=self.service,
            diagnosis="Metrics, logs, and deployments support a controlled restart.",
            proposed_action=ActionProposal(action_type="restart_service", target=self.service,
                                           reason="Trace flow verification", evidence=[],
                                           risk_level="HIGH", status="proposed"),
        )


def test_completed_run_reconstructs_investigation_approval_and_execution(database_path):
    init_db(database_path)
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    service = f"trace-full-{uuid4().hex}"
    with get_connection(database_path) as connection:
        row = connection.execute(
            "INSERT INTO services (name, environment, repository, current_state) VALUES (%s, 'production', %s, 'degraded') RETURNING id",
            (service, f"trace/{service}"),
        ).fetchone()
        connection.execute(
            "INSERT INTO metrics (timestamp, service_id, metric_name, value) VALUES (NOW(), %s, 'http_request_latency_ms', 1320.0)",
            (row["id"],),
        )
    principal = UserPrincipal(username="trace-owner", role="operator")
    agent = build_agent(database_path, TraceProvider(service))
    state = asyncio.run(agent.investigate("Investigate elevated service latency.", principal))
    assert state.status == "paused" and state.approval is not None
    agent.approval_service.decide(state.approval.id, "approved", principal, "Trace test approval")

    trace = AgentEventRepository(database_path).for_run(state.run_id, principal)

    assert isinstance(trace, AgentRunTrace)
    assert trace.status == "completed"
    assert trace.service == service
    assert [event.event_type for event in trace.events] == [
        "run.started", "retrieval", "classify", "metrics", "planning", "logs",
        "planning", "deployment", "diagnosis", "action_proposed", "policy", "approval", "run.paused",
        "approval", "execution", "verification", "run.completed",
    ]
    for event in trace.events:
        assert event.run_id == state.run_id
        assert event.timestamp is not None
        assert event.status
    duration_events = {"retrieval", "classify", "planning", "metrics", "logs", "deployment", "diagnosis"}
    assert all(event.duration_ms is not None and event.duration_ms >= 0
               for event in trace.events if event.event_type in duration_events)
    model_events = [event for event in trace.events if event.event_type in {"classify", "planning", "diagnosis"}]
    assert all(event.model == "test-trace-model" for event in model_events)
    assert [event.tool for event in trace.events if event.event_type in {"metrics", "logs", "deployment"}] == [
        "get_metrics", "search_logs", "get_recent_deployments",
    ]
    assert [event.status for event in trace.events if event.event_type == "approval"] == ["pending", "approved"]
    assert [event.status for event in trace.events if event.event_type == "verification"] == ["SUCCESS"]
    assert trace.events[-1].event_type == "run.completed"


def test_trace_api_requires_auth_and_viewers_only_read_their_own_runs(database_path, api, monkeypatch):
    init_db(database_path)
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    monkeypatch.setattr(ops_agent, "provider", TraceProvider())
    owner_token = AuthService().issue_token(UserPrincipal(username="trace-api-owner", role="viewer"))
    created = api(
        "POST", "/agent/investigate", json={"request": "Investigate payments latency."},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]

    anonymous = api("GET", f"/agent/runs/{run_id}/events")
    assert anonymous.status_code == 401
    own_trace = api("GET", f"/agent/runs/{run_id}/events", headers={"Authorization": f"Bearer {owner_token}"})
    assert own_trace.status_code == 200
    assert own_trace.json()["run_id"] == run_id
    assert own_trace.json()["events"]

    other_token = AuthService().issue_token(UserPrincipal(username="different-viewer", role="viewer"))
    hidden_trace = api("GET", f"/agent/runs/{run_id}/events", headers={"Authorization": f"Bearer {other_token}"})
    assert hidden_trace.status_code == 404
