from app.approval.repository import ApprovalConflict, ApprovalRepository
from app.approval.schemas import ApprovalRecord
from app.auth.schemas import UserPrincipal


class ApprovalAuthorizationError(Exception):
    pass


class SimulatedActionExecutor:
    def execute(self, proposal) -> dict:
        return {
            "status": "simulated",
            "action_type": proposal.action_type,
            "target": proposal.target,
            "message": "No real infrastructure was changed.",
        }


class ApprovalService:
    def __init__(self, repository: ApprovalRepository, executor: SimulatedActionExecutor | None = None):
        self.repository = repository
        self.executor = executor or SimulatedActionExecutor()

    def get(self, approval_id: int) -> ApprovalRecord:
        return self.repository.get(approval_id)

    def decide(self, approval_id: int, decision: str, principal: UserPrincipal, reason: str) -> ApprovalRecord:
        if principal.role not in {"operator", "admin"}:
            raise ApprovalAuthorizationError
        record = self.repository.get(approval_id)
        if record.decision != "pending":
            raise ApprovalConflict(f"Approval already decided: {record.decision}")
        result = self.executor.execute(record.proposal) if decision == "approved" else None
        return self.repository.decide(approval_id, decision, principal.username, reason, result)
