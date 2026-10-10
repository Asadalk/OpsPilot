from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.actions.schemas import ActionProposal

ApprovalDecision = Literal["pending", "approved", "rejected", "expired"]


class ApprovalRecord(BaseModel):
    id: int
    run_id: UUID
    action_id: UUID
    idempotency_key: str
    requested_at: datetime
    expires_at: datetime
    decided_at: datetime | None
    decision: ApprovalDecision
    decided_by: str | None
    reason: str | None
    proposal: ActionProposal
    execution_result: dict[str, Any] | None = None
    requested_by: str | None = None


class ApprovalDecisionRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)
