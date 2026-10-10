from typing import Literal

from pydantic import BaseModel

from app.actions.schemas import ActionProposal, ActionType, RiskLevel
from app.auth.schemas import UserPrincipal

PolicyOutcome = Literal["allow", "deny", "require_approval"]

RISK_BY_ACTION: dict[ActionType, RiskLevel] = {
    "create_incident": "MEDIUM",
    "update_incident": "MEDIUM",
    "create_github_issue": "MEDIUM",
    "generate_report": "LOW",
    "restart_service": "HIGH",
    "rollback_deployment": "HIGH",
    "delete_data": "CRITICAL",
}


class PolicyDecision(BaseModel):
    outcome: PolicyOutcome
    reason: str
    username: str
    role: str
    action_type: str
    environment: str
    risk_level: RiskLevel


# (role, canonical risk) -> (outcome in production, outcome elsewhere).
# Production is stricter: operators need approval for HIGH risk there, and CRITICAL
# actions are never permitted in production.
POLICY_RULES: dict[tuple[str, RiskLevel], tuple[PolicyOutcome, PolicyOutcome]] = {
    ("viewer", "LOW"): ("allow", "allow"),
    ("viewer", "MEDIUM"): ("deny", "deny"),
    ("viewer", "HIGH"): ("deny", "deny"),
    ("viewer", "CRITICAL"): ("deny", "deny"),
    ("operator", "LOW"): ("allow", "allow"),
    ("operator", "MEDIUM"): ("allow", "allow"),
    ("operator", "HIGH"): ("require_approval", "allow"),
    ("operator", "CRITICAL"): ("deny", "require_approval"),
    ("admin", "LOW"): ("allow", "allow"),
    ("admin", "MEDIUM"): ("allow", "allow"),
    ("admin", "HIGH"): ("allow", "allow"),
    ("admin", "CRITICAL"): ("deny", "require_approval"),
}


class PolicyEngine:
    def evaluate(self, proposal: ActionProposal, principal: UserPrincipal, environment: str) -> PolicyDecision:
        # Risk comes from the server table, never from the model's proposal.
        risk = RISK_BY_ACTION[proposal.action_type]
        production_outcome, other_outcome = POLICY_RULES[(principal.role, risk)]
        outcome = production_outcome if environment == "production" else other_outcome
        return PolicyDecision(
            outcome=outcome,
            reason=f"{principal.role} policy evaluated {proposal.action_type} in {environment} as {risk} risk.",
            username=principal.username,
            role=principal.role,
            action_type=proposal.action_type,
            environment=environment,
            risk_level=risk,
        )