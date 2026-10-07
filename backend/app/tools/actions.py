from app.actions.schemas import ActionProposal, ActionProposalInput, RiskLevel
from app.tools.base import Tool


RISK_BY_ACTION: dict[str, RiskLevel] = {
    "create_incident": "medium",
    "update_incident": "medium",
    "create_github_issue": "medium",
    "generate_report": "low",
    "restart_service": "high",
    "rollback_deployment": "high",
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