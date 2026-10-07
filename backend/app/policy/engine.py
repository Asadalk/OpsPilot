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
    "send_notification": "MEDIUM",
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


class PolicyEngine:
    def evaluate(self, proposal: ActionProposal, principal: UserPrincipal, environment: str) -> PolicyDecision:
        risk = RISK_BY_ACTION[proposal.action_type]
        if principal.role == "viewer":
            outcome: PolicyOutcome = "allow" if risk == "LOW" else "deny"
        elif principal.role == "operator":
            outcome = "allow" if risk in {"LOW", "MEDIUM"} else "require_approval"
        else:
            outcome = "allow" if risk in {"LOW", "MEDIUM", "HIGH"} else "require_approval"
        return PolicyDecision(
            outcome=outcome,
            reason=f"{principal.role} policy evaluated {proposal.action_type} in {environment} as {risk} risk.",
            username=principal.username,
            role=principal.role,
            action_type=proposal.action_type,
            environment=environment,
            risk_level=risk,
        )