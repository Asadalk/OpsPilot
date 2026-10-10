from app.actions.schemas import ActionProposal, ActionProposalInput
from app.policy.engine import RISK_BY_ACTION
from app.tools.base import Tool




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