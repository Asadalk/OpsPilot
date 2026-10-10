from app.actions.schemas import ActionProposal
from app.agent.agent import build_agent
from app.agent.schemas import AgentDecision
from app.auth.schemas import UserPrincipal
from app.db.database import init_db
from app.rag.ingest import ingest_directory
from app.policy.engine import PolicyEngine
from pathlib import Path
import asyncio


def restart_proposal() -> ActionProposal:
    return ActionProposal(
        action_type="restart_service",
        target="payments-api",
        reason="Attempted policy bypass test.",
        evidence=[],
        risk_level="LOW",
        status="proposed",
    )


def test_rbac_policy_viewer_denies_restart_even_when_llm_claims_low_risk():
    decision = PolicyEngine().evaluate(restart_proposal(), UserPrincipal(username="v", role="viewer"), "production")
    assert decision.outcome == "deny"
    assert decision.risk_level == "HIGH"


def test_rbac_policy_operator_requires_approval_for_restart():
    decision = PolicyEngine().evaluate(restart_proposal(), UserPrincipal(username="o", role="operator"), "production")
    assert decision.outcome == "require_approval"
    assert decision.environment == "production"


def test_rbac_policy_admin_allows_configured_high_risk_restart():
    decision = PolicyEngine().evaluate(restart_proposal(), UserPrincipal(username="a", role="admin"), "production")
    assert decision.outcome == "allow"
    assert decision.risk_level == "HIGH"


def proposal(action_type: str, target: str = "payments-api") -> ActionProposal:
    return ActionProposal(action_type=action_type, target=target, reason="Policy environment test.",
                          evidence=[], risk_level="LOW", status="proposed")


def test_policy_environment_changes_operator_high_risk_outcome():
    operator = UserPrincipal(username="o", role="operator")
    assert PolicyEngine().evaluate(proposal("restart_service"), operator, "production").outcome == "require_approval"
    assert PolicyEngine().evaluate(proposal("restart_service", "catalog-api"), operator, "staging").outcome == "allow"


def test_policy_never_permits_critical_actions_in_production():
    for role in ("viewer", "operator", "admin"):
        decision = PolicyEngine().evaluate(proposal("delete_data"), UserPrincipal(username=role, role=role), "production")
        assert decision.outcome == "deny", role
    admin = UserPrincipal(username="a", role="admin")
    assert PolicyEngine().evaluate(proposal("delete_data"), admin, "staging").outcome == "require_approval"


def test_policy_table_covers_every_role_and_risk():
    from typing import get_args

    from app.actions.schemas import RiskLevel
    from app.policy.engine import POLICY_RULES

    from app.auth.schemas import Role

    assert set(POLICY_RULES) == {(role, risk) for role in get_args(Role) for risk in get_args(RiskLevel)}


class SpoofedRiskProvider:
    async def decide(self, _state, _tools):
        return AgentDecision(
            action="diagnose",
            service="payments-api",
            diagnosis="A restart is suggested.",
            proposed_action=ActionProposal(
                action_type="restart_service",
                target="payments-api",
                reason="The model claims this is low risk.",
                evidence=[],
                risk_level="LOW",
                status="proposed",
            ),
        )


def test_agent_cannot_bypass_policy_with_spoofed_risk(database_path):
    init_db(database_path)
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    agent = build_agent(database_path, SpoofedRiskProvider())

    state = asyncio.run(
        agent.investigate(
            "Restart payments-api",
            UserPrincipal(username="viewer", role="viewer"),
        )
    )

    assert state.policy_decision.outcome == "deny"
    assert state.policy_decision.risk_level == "HIGH"
    assert state.proposed_action.status == "denied"