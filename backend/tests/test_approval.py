import asyncio
from pathlib import Path
from uuid import uuid4

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
    def __init__(self, action_type="restart_service", target="payments-api"):
        self.action_type = action_type
        self.target = target

    async def decide(self, _state, _tools):
        return AgentDecision(
            action="diagnose",
            service=self.target,
            diagnosis=f"{self.action_type} requires a human decision.",
            proposed_action=ActionProposal(
                action_type=self.action_type,
                target=self.target,
                reason="High latency persists after investigation.",
                evidence=[{"tool": "get_metrics", "metric": "http_request_latency_ms"}],
                risk_level="HIGH",
                status="proposed",
            ),
        )


class FlagshipPaymentProvider:
    async def decide(self, state, _tools):
        if not state.tool_calls:
            return AgentDecision(
                action="call_tool", tool_name="get_service_health",
                arguments={"service": "payments-api"}, service="payments-api", severity="sev2",
            )
        if len(state.tool_calls) == 1:
            return AgentDecision(
                action="call_tool", tool_name="get_metrics",
                arguments={"service": "payments-api"}, service="payments-api", severity="sev2",
            )
        return AgentDecision(
            action="diagnose",
            service="payments-api",
            severity="sev2",
            diagnosis="Payments latency is elevated while the service is degraded; restart is the controlled recovery action.",
            proposed_action=ActionProposal(
                action_type="restart_service",
                target="payments-api",
                reason="Investigated latency is above the expected baseline.",
                evidence=[{"tool": "get_metrics", "result": state.tool_results[-1]["result"]}],
                risk_level="HIGH",
                status="proposed",
            ),
        )


def reset_payments_scenario(database_path):
    with get_connection(database_path) as connection:
        service = connection.execute("SELECT id FROM services WHERE name = 'payments-api'").fetchone()
        connection.execute("UPDATE services SET current_state = 'degraded' WHERE id = %s", (service["id"],))
        connection.execute("DELETE FROM metrics WHERE service_id = %s", (service["id"],))
        connection.execute(
            "INSERT INTO metrics (timestamp, service_id, metric_name, value) VALUES (NOW(), %s, 'http_request_latency_ms', 1842.0)",
            (service["id"],),
        )
        connection.execute("UPDATE incidents SET status = 'investigating' WHERE service_id = %s AND title = 'Payments latency spike'", (service["id"],))
        connection.execute("DELETE FROM logs WHERE service_id = %s AND message = 'Simulated restart completed.'", (service["id"],))


@pytest.fixture(autouse=True)
def restore_seed_scenario(database_path):
    yield
    reset_payments_scenario(database_path)


def setup(database_path):
    init_db(database_path)
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    reset_payments_scenario(database_path)


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
        service = connection.execute("SELECT current_state FROM services WHERE name = 'payments-api'").fetchone()
    assert action["status"] == "rejected"
    assert service["current_state"] == "degraded"


def test_restart_is_verified_and_resolves_flagship_incident(database_path):
    setup(database_path)
    agent = build_agent(database_path, FlagshipPaymentProvider())
    operator = UserPrincipal(username="operator", role="operator")
    state = asyncio.run(agent.investigate("Investigate the payments latency incident and restore service if the evidence supports it.", operator))
    assert state.diagnosis.startswith("Payments latency is elevated")
    assert len(state.tool_calls) == 2
    assert state.tool_results[-1]["result"]["metrics"][0]["value"] == 1842.0

    approved = agent.approval_service.decide(state.approval.id, "approved", operator, "Restart approved")
    result = approved.execution_result
    assert result["verification"]["status"] == "SUCCESS"
    assert result["verification"]["attempt_count"] == 1
    assert result["pre_action_state"]["state"] == "degraded"
    assert result["post_action_state"]["state"] == "healthy"
    attempt = result["verification"]["attempts"][0]
    assert attempt["before"]["metrics"]["http_request_latency_ms"] == 1842.0
    assert attempt["after"]["metrics"]["http_request_latency_ms"] == 460.5
    assert result["resolved_incident_ids"]
    with get_connection(database_path) as connection:
        incident = connection.execute("SELECT status FROM incidents WHERE id = %s", (result["resolved_incident_ids"][0],)).fetchone()
    assert incident["status"] == "resolved"
    persisted = ApprovalRepository(database_path).get(approved.id)
    assert persisted.execution_result["verification"]["status"] == "SUCCESS"


def test_failed_rollback_reinvestigates_then_escalates_after_two_attempts(database_path):
    setup(database_path)
    service_name = f"rollback-empty-{uuid4()}"
    with get_connection(database_path) as connection:
        service = connection.execute(
            "INSERT INTO services (name, environment, repository, current_state) VALUES (%s, 'production', %s, 'degraded') RETURNING id",
            (service_name, f"example/{service_name}"),
        ).fetchone()
        connection.execute(
            "INSERT INTO deployments (service_id, version, deployed_at, author, status) VALUES (%s, 'v1', NOW(), 'test', 'success')",
            (service["id"],),
        )
    agent = build_agent(database_path, HighRiskProvider("rollback_deployment", service_name))
    operator = UserPrincipal(username="operator", role="operator")
    state = asyncio.run(agent.investigate(f"Rollback {service_name}", operator))

    approved = agent.approval_service.decide(state.approval.id, "approved", operator, "Rollback approved")
    verification = approved.execution_result["verification"]
    assert verification["status"] == "FAILED"
    assert verification["attempt_count"] == 2
    assert verification["max_automatic_attempts"] == 2
    assert verification["escalated"] is True
    assert "reinvestigation" in verification["attempts"][0]
    assert approved.execution_result["resolved_incident_ids"] == []


def test_rollback_restores_previous_successful_deployment(database_path):
    setup(database_path)
    service_name = f"rollback-ready-{uuid4()}"
    with get_connection(database_path) as connection:
        service = connection.execute(
            "INSERT INTO services (name, environment, repository, current_state) VALUES (%s, 'production', %s, 'degraded') RETURNING id",
            (service_name, f"example/{service_name}"),
        ).fetchone()
        connection.execute(
            "INSERT INTO deployments (service_id, version, deployed_at, author, status) VALUES "
            "(%s, 'v1', NOW() - INTERVAL '2 hours', 'test', 'success'), "
            "(%s, 'v2', NOW() - INTERVAL '1 hour', 'test', 'success')",
            (service["id"], service["id"]),
        )
        connection.execute(
            "INSERT INTO metrics (timestamp, service_id, metric_name, value) VALUES (NOW(), %s, 'http_5xx_rate', 12.0)",
            (service["id"],),
        )
    agent = build_agent(database_path, HighRiskProvider("rollback_deployment", service_name))
    operator = UserPrincipal(username="operator", role="operator")
    state = asyncio.run(agent.investigate(f"Rollback {service_name}", operator))

    approved = agent.approval_service.decide(state.approval.id, "approved", operator, "Rollback approved")
    result = approved.execution_result
    assert result["verification"]["status"] == "SUCCESS"
    assert result["verification"]["attempts"][0]["execution"]["restored_version"] == "v1"
    with get_connection(database_path) as connection:
        service_row = connection.execute("SELECT current_state FROM services WHERE id = %s", (service["id"],)).fetchone()
        deployment = connection.execute("SELECT version, status FROM deployments WHERE service_id = %s AND version = 'v2'", (service["id"],)).fetchone()
    assert service_row["current_state"] == "healthy"
    assert deployment["status"] == "rolled_back"


def test_restart_without_observable_evidence_is_inconclusive(database_path):
    setup(database_path)
    service_name = f"verification-empty-{uuid4()}"
    with get_connection(database_path) as connection:
        connection.execute(
            "INSERT INTO services (name, environment, repository, current_state) VALUES (%s, 'staging', %s, 'healthy')",
            (service_name, f"example/{service_name}"),
        )
    agent = build_agent(database_path, HighRiskProvider("restart_service", service_name))
    operator = UserPrincipal(username="operator", role="operator")
    state = asyncio.run(agent.investigate(f"Restart {service_name}", operator))

    approved = agent.approval_service.decide(state.approval.id, "approved", operator, "Restart approved")
    verification = approved.execution_result["verification"]
    assert verification["status"] == "INCONCLUSIVE"
    assert verification["attempt_count"] == 1
    assert verification["escalated"] is True


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
    assert state.approval.id in [item["id"] for item in pending.json()]

    response = api(
        "POST", f"/approvals/{state.approval.id}/approve", headers=headers,
        json={"reason": "Reviewed incident evidence"},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "approved"
    assert response.json()["execution_result"]["status"] == "simulated"
    assert response.json()["execution_result"]["verification"]["status"] == "SUCCESS"
