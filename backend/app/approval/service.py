from typing import Literal

import psycopg

from app.actions.schemas import ActionProposal
from app.approval.repository import ApprovalRepository
from app.approval.schemas import ApprovalRecord
from app.auth.schemas import UserPrincipal
from app.db.simulator_actions import SimulatorActionRepository


class ApprovalAuthorizationError(Exception):
    pass


class SimulatedActionExecutor:
    def __init__(self, repository: SimulatorActionRepository | None = None):
        self.repository = repository or SimulatorActionRepository()

    def execute(self, connection: psycopg.Connection, proposal: ActionProposal) -> dict:
        return self.repository.execute(connection, proposal)


class ApprovalService:
    def __init__(self, repository: ApprovalRepository, executor: SimulatedActionExecutor | None = None):
        self.repository = repository
        self.executor = executor or SimulatedActionExecutor()

    def get(self, approval_id: int) -> ApprovalRecord:
        return self.repository.get(approval_id)

    def decide(self, approval_id: int, decision: Literal["approved", "rejected"], principal: UserPrincipal, reason: str) -> ApprovalRecord:
        if principal.role not in {"operator", "admin"}:
            raise ApprovalAuthorizationError("Approval authority required")
        if self.repository.get(approval_id).requested_by == principal.username:
            raise ApprovalAuthorizationError("The requester cannot decide their own action")
        execute = self.executor.execute if decision == "approved" else None
        return self.repository.decide(approval_id, decision, principal.username, reason, execute)

    def execute_allowed(self, approval_id: int, principal: UserPrincipal) -> ApprovalRecord:
        """Run an action the policy engine allowed outright, recorded as a policy decision, not a human one."""
        return self.repository.decide(approval_id, "approved", f"policy:{principal.username}",
                                      "Allowed by server policy without human approval.", self.executor.execute)
