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



# A different operator from the requester, because requesters cannot approve their own actions.
REVIEWER = UserPrincipal(username="reviewer", role="operator")

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
    assert repeated.idempotency_key == state.approval.idempotency_key

    approved = agent.approval_service.decide(state.approval.id, "approved", REVIEWER, "Incident review approved")
    assert approved.decision == "approved"
    assert approved.execution_result["status"] == "simulated"

    # Model a lost HTTP response: the approval committed, but the client retries
    # the same request and must receive the persisted result without another write.
    with get_connection(database_path) as connection:
        side_effect_count_before_retry = connection.execute(
            "SELECT COUNT(*) AS count FROM logs WHERE message = 'Simulated restart completed.'"
        ).fetchone()["count"]
    retried = agent.approval_service.decide(state.approval.id, "approved", REVIEWER, "Incident review approved")
    assert retried.execution_result == approved.execution_result
    assert retried.action_id == approved.action_id

    with get_connection(database_path) as connection:
        action = connection.execute("SELECT status, idempotency_key FROM actions WHERE action_id = %s", (approved.action_id,)).fetchone()
        run = connection.execute("SELECT status FROM agent_runs WHERE run_id = %s", (state.run_id,)).fetchone()
    assert action["status"] == "executed"
    assert run["status"] == "completed"
    assert action["idempotency_key"] == approved.idempotency_key
    with get_connection(database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) AS count FROM logs WHERE message = 'Simulated restart completed.'"
        ).fetchone()["count"] == side_effect_count_before_retry
        assert connection.execute("SELECT COUNT(*) AS count FROM actions WHERE run_id = %s", (state.run_id,)).fetchone()["count"] == 1
        assert connection.execute(
            "SELECT COUNT(*) AS count FROM audit_events WHERE run_id = %s AND event_type = 'action.executed'",
            (state.run_id,),
        ).fetchone()["count"] == 1
    from app.audit.repository import AuditRepository
    with get_connection(database_path) as connection:
        incident = connection.execute("SELECT id FROM incidents WHERE title='Payments latency spike'").fetchone()
    story = AuditRepository(database_path).incident_story(incident["id"])
    event_types = [event.event_type for event in story.events]
    assert "incident.created" in event_types
    assert "agent.started" in event_types
    assert "tool.called" in event_types
    assert "action.proposed" in event_types
    assert "approval.requested" in event_types
    assert "approval.granted" in event_types
    assert "action.executed" in event_types
    assert "verification.completed" in event_types
    assert "incident.resolved" in event_types

    with pytest.raises(ApprovalConflict):
        agent.approval_service.decide(state.approval.id, "rejected", REVIEWER, "Conflicting retry")


def test_reject_and_unauthorized_approval(database_path):
    setup(database_path)
    agent = build_agent(database_path, HighRiskProvider())
    operator = UserPrincipal(username="operator", role="operator")
    viewer = UserPrincipal(username="viewer", role="viewer")

    state = asyncio.run(agent.investigate("Restart payments-api", operator))
    with pytest.raises(ApprovalAuthorizationError):
        agent.approval_service.decide(state.approval.id, "approved", viewer, "not allowed")

    rejected = agent.approval_service.decide(state.approval.id, "rejected", REVIEWER, "Risk not accepted")
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

    approved = agent.approval_service.decide(state.approval.id, "approved", REVIEWER, "Restart approved")
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

    approved = agent.approval_service.decide(state.approval.id, "approved", REVIEWER, "Rollback approved")
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

    approved = agent.approval_service.decide(state.approval.id, "approved", REVIEWER, "Rollback approved")
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
            "INSERT INTO services (name, environment, repository, current_state) VALUES (%s, 'production', %s, 'healthy')",
            (service_name, f"example/{service_name}"),
        )
    agent = build_agent(database_path, HighRiskProvider("restart_service", service_name))
    operator = UserPrincipal(username="operator", role="operator")
    state = asyncio.run(agent.investigate(f"Restart {service_name}", operator))

    approved = agent.approval_service.decide(state.approval.id, "approved", REVIEWER, "Restart approved")
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
    from app.audit.repository import AuditRepository
    with get_connection(database_path) as connection:
        incident_id = connection.execute("SELECT id FROM incidents WHERE title='Payments latency spike'").fetchone()["id"]
    story = AuditRepository(database_path).incident_story(incident_id)
    assert any(event.event_type == "approval.expired" for event in story.events)
    with pytest.raises(ApprovalConflict):
        agent.approval_service.decide(expired.id, "approved", REVIEWER, "too late")


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

    self_approval = api(
        "POST", f"/approvals/{state.approval.id}/approve", headers=headers,
        json={"reason": "Approving my own request"},
    )
    assert self_approval.status_code == 403
    assert self_approval.json()["detail"] == "The requester cannot decide their own action"
    reviewer_headers = {"Authorization": f"Bearer {AuthService().issue_token(REVIEWER)}"}
    response = api(
        "POST", f"/approvals/{state.approval.id}/approve", headers=reviewer_headers,
        json={"reason": "Reviewed incident evidence"},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "approved"
    assert response.json()["execution_result"]["status"] == "simulated"
    assert response.json()["execution_result"]["verification"]["status"] == "SUCCESS"
    with get_connection(database_path) as connection:
        incident_id = connection.execute("SELECT id FROM incidents WHERE title='Payments latency spike'").fetchone()["id"]
    story = api("GET", f"/audit/incidents/{incident_id}", headers=headers)
    assert story.status_code == 200
    assert story.json()["incident"]["title"] == "Payments latency spike"
    assert any(event["event_type"] == "incident.resolved" for event in story.json()["events"])


def faulty_service(database_path, prefix: str, fault: str) -> str:
    service_name = f"{prefix}-{uuid4()}"
    with get_connection(database_path) as connection:
        service = connection.execute(
            "INSERT INTO services (name, environment, repository, current_state, fault) "
            "VALUES (%s, 'production', %s, 'degraded', %s) RETURNING id",
            (service_name, f"example/{service_name}", fault),
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
        connection.execute(
            "INSERT INTO incidents (title, severity, status, service_id) VALUES (%s, 'sev2', 'investigating', %s)",
            (f"Fault test {service_name}", service["id"]),
        )
    return service_name


def approve_proposal(database_path, action_type: str, service_name: str) -> dict:
    agent = build_agent(database_path, HighRiskProvider(action_type, service_name))
    operator = UserPrincipal(username="operator", role="operator")
    state = asyncio.run(agent.investigate(f"{action_type} {service_name}", operator))
    return agent.approval_service.decide(state.approval.id, "approved", REVIEWER, "Approved").execution_result


def test_restart_does_not_fix_a_bad_deployment_and_escalates(database_path):
    setup(database_path)
    service_name = faulty_service(database_path, "fault-bad-deploy", "bad_deployment")
    result = approve_proposal(database_path, "restart_service", service_name)
    verification = result["verification"]
    assert verification["status"] == "FAILED"
    assert verification["attempt_count"] == 2
    assert verification["escalated"] is True
    assert result["resolved_incident_ids"] == []
    assert result["post_action_state"]["state"] == "degraded"


def test_rollback_fixes_a_bad_deployment(database_path):
    setup(database_path)
    service_name = faulty_service(database_path, "fault-bad-deploy", "bad_deployment")
    result = approve_proposal(database_path, "rollback_deployment", service_name)
    assert result["verification"]["status"] == "SUCCESS"
    assert len(result["resolved_incident_ids"]) == 1


def test_no_action_on_the_service_fixes_an_external_dependency(database_path):
    setup(database_path)
    for action_type in ("restart_service", "rollback_deployment"):
        service_name = faulty_service(database_path, "fault-dependency", "external_dependency")
        result = approve_proposal(database_path, action_type, service_name)
        assert result["verification"]["status"] == "FAILED", action_type
        assert result["resolved_incident_ids"] == []


def test_policy_allowed_staging_restart_executes_as_a_recorded_policy_decision(database_path):
    setup(database_path)
    service_name = f"staging-pool-{uuid4()}"
    with get_connection(database_path) as connection:
        service = connection.execute(
            "INSERT INTO services (name, environment, repository, current_state, fault) "
            "VALUES (%s, 'staging', %s, 'degraded', 'connection_pool_exhaustion') RETURNING id",
            (service_name, f"example/{service_name}"),
        ).fetchone()
        connection.execute(
            "INSERT INTO metrics (timestamp, service_id, metric_name, value) VALUES (NOW(), %s, 'http_request_latency_ms', 900.0)",
            (service["id"],),
        )
    agent = build_agent(database_path, HighRiskProvider("restart_service", service_name))
    operator = UserPrincipal(username="operator", role="operator")
    state = asyncio.run(agent.investigate(f"Restart {service_name}", operator))

    assert state.policy_decision.outcome == "allow"
    assert state.status == "completed"
    assert state.approval.decision == "approved"
    assert state.approval.decided_by == "policy:operator"
    assert state.approval.execution_result["verification"]["status"] == "SUCCESS"
    with get_connection(database_path) as connection:
        run = connection.execute("SELECT status, diagnosis FROM agent_runs WHERE run_id = %s", (state.run_id,)).fetchone()
    assert run["status"] == "completed"
    assert "Policy allowed execution; verification SUCCESS" in run["diagnosis"]


def test_approval_outcome_is_appended_to_the_agent_diagnosis(database_path):
    setup(database_path)
    service_name = faulty_service(database_path, "diagnosis-kept", "connection_pool_exhaustion")
    agent = build_agent(database_path, HighRiskProvider("restart_service", service_name))
    state = asyncio.run(agent.investigate(f"Restart {service_name}", UserPrincipal(username="operator", role="operator")))
    agent.approval_service.decide(state.approval.id, "approved", REVIEWER, "Approved")
    with get_connection(database_path) as connection:
        diagnosis = connection.execute("SELECT diagnosis FROM agent_runs WHERE run_id = %s", (state.run_id,)).fetchone()["diagnosis"]
    assert diagnosis.startswith(state.diagnosis)
    assert "\n\nHuman approval granted; verification SUCCESS" in diagnosis
