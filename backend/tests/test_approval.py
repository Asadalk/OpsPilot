import asyncio
from pathlib import Path

import pytest

from app.actions.schemas import ActionProposal
from app.agent.agent import build_agent
from app.agent.schemas import AgentDecision
from app.approval.repository import ApprovalConflict, ApprovalRepository
from app.approval.service import ApprovalAuthorizationError
from app.auth.schemas import UserPrincipal
from app.auth.service import AuthService
from app.db.database import get_connection, init_db
from app.rag.ingest import ingest_directory


class HighRiskProvider:
    async def decide(self, _state, _tools):
        return AgentDecision(
            action="diagnose",
            service="payments-api",
            diagnosis="Restart requires a human decision.",
            proposed_action=ActionProposal(
                action_type="restart_service",
                target="payments-api",
                reason="High latency persists after investigation.",
                evidence=[{"tool": "get_metrics", "metric": "http_request_latency_ms"}],
                risk_level="HIGH",
                status="proposed",
            ),
        )


def setup(database_path):
    init_db(database_path)
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)


def test_high_risk_action_pauses_then_approves_and_executes(database_path):
    setup(database_path)
    agent = build_agent(database_path, HighRiskProvider())
    operator = UserPrincipal(username="operator", role="operator")

    state = asyncio.run(agent.investigate("Restart payments-api", operator))
    assert state.status == "paused"
    assert state.approval is not None
    assert state.approval.decision == "pending"
    assert state.proposed_action.status == "approval_required"
    after_restart = ApprovalRepository(database_path).get(state.approval.id)
    assert after_restart.decision == "pending"
    with get_connection(database_path) as connection:
        paused_run = connection.execute("SELECT status, completed_at FROM agent_runs WHERE run_id = %s", (state.run_id,)).fetchone()
    assert paused_run == {"status": "paused", "completed_at": None}
    repeated = agent.approval_service.repository.create_pending(state.run_id, state.proposed_action)
    assert repeated.id == state.approval.id

    approved = agent.approval_service.decide(state.approval.id, "approved", operator, "Incident review approved")
    assert approved.decision == "approved"
    assert approved.execution_result["status"] == "simulated"

    with get_connection(database_path) as connection:
        action = connection.execute("SELECT status FROM actions WHERE action_id = %s", (approved.action_id,)).fetchone()
        run = connection.execute("SELECT status FROM agent_runs WHERE run_id = %s", (state.run_id,)).fetchone()
    assert action["status"] == "executed"
    assert run["status"] == "completed"

    with pytest.raises(ApprovalConflict):
        agent.approval_service.decide(state.approval.id, "approved", operator, "duplicate")


def test_reject_and_unauthorized_approval(database_path):
    setup(database_path)
    agent = build_agent(database_path, HighRiskProvider())
    operator = UserPrincipal(username="operator", role="operator")
    viewer = UserPrincipal(username="viewer", role="viewer")

    state = asyncio.run(agent.investigate("Restart payments-api", operator))
    with pytest.raises(ApprovalAuthorizationError):
        agent.approval_service.decide(state.approval.id, "approved", viewer, "not allowed")

    rejected = agent.approval_service.decide(state.approval.id, "rejected", operator, "Risk not accepted")
    assert rejected.decision == "rejected"
    assert rejected.execution_result is None
    with get_connection(database_path) as connection:
        action = connection.execute("SELECT status FROM actions WHERE action_id = %s", (rejected.action_id,)).fetchone()
    assert action["status"] == "rejected"


def test_expired_approval_is_closed_without_executing(database_path):
    setup(database_path)
    agent = build_agent(database_path, HighRiskProvider())
    operator = UserPrincipal(username="operator", role="operator")
    state = asyncio.run(agent.investigate("Restart payments-api", operator))
    with get_connection(database_path) as connection:
        connection.execute("UPDATE approvals SET expires_at = NOW() - INTERVAL '1 minute' WHERE id = %s", (state.approval.id,))

    expired = ApprovalRepository(database_path).get(state.approval.id)
    assert expired.decision == "expired"
    with get_connection(database_path) as connection:
        action = connection.execute("SELECT status FROM actions WHERE action_id = %s", (expired.action_id,)).fetchone()
        run = connection.execute("SELECT status, diagnosis FROM agent_runs WHERE run_id = %s", (state.run_id,)).fetchone()
    assert action["status"] == "expired"
    assert run["status"] == "completed"
    assert "expired" in run["diagnosis"]
    with pytest.raises(ApprovalConflict):
        agent.approval_service.decide(expired.id, "approved", operator, "too late")


def test_approval_api_authenticates_and_records_decision(database_path, api, monkeypatch):
    setup(database_path)
    agent = build_agent(database_path, HighRiskProvider())
    operator = UserPrincipal(username="operator", role="operator")
    state = asyncio.run(agent.investigate("Restart payments-api", operator))
    from app.main import ops_agent
    monkeypatch.setattr(ops_agent.approval_service.repository, "database_url", database_path)

    assert api("GET", "/approvals").status_code == 401
    token = AuthService().issue_token(operator)
    headers = {"Authorization": f"Bearer {token}"}
    pending = api("GET", "/approvals", headers=headers)
    assert pending.status_code == 200
    assert [item["id"] for item in pending.json()] == [state.approval.id]

    response = api(
        "POST", f"/approvals/{state.approval.id}/approve", headers=headers,
        json={"reason": "Reviewed incident evidence"},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "approved"
    assert response.json()["execution_result"]["status"] == "simulated"
