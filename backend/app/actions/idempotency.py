from uuid import UUID

from app.actions.schemas import ActionProposal


def action_idempotency_key(run_id: UUID, proposal: ActionProposal) -> str:
    """Return the stable execution identity for an action proposed in a run."""
    action_type = proposal.action_type.strip().lower()
    target = proposal.target.strip().lower()
    return f"{run_id}:{action_type}:{target}"
