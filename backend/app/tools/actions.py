from app.actions.schemas import ActionProposal, ActionProposalInput, RiskLevel
from app.tools.base import Tool


RISK_BY_ACTION: dict[str, RiskLevel] = {
    "create_incident": "MEDIUM",
    "update_incident": "MEDIUM",
    "create_github_issue": "MEDIUM",
    "generate_report": "LOW",
    "send_notification": "MEDIUM",
    "restart_service": "HIGH",
    "rollback_deployment": "HIGH",
    "delete_data": "CRITICAL",
}


class ProposeAction(Tool[ActionProposalInput, ActionProposal]):
    name = "propose_action"
    description = "Create a deterministic action proposal; never execute the action."
    kind = "write"
    input_schema = ActionProposalInput
    result_schema = ActionProposal

    def execute(self, parameters: ActionProposalInput) -> ActionProposal:
        return ActionProposal(
            action_type=parameters.action_type,
            target=parameters.target,
            reason=parameters.reason,
            evidence=parameters.evidence,
            risk_level=RISK_BY_ACTION[parameters.action_type],
            status="proposed",
        )