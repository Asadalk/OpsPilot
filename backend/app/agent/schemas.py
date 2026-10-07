from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.actions.schemas import ActionProposal
from app.approval.schemas import ApprovalRecord
from app.policy.engine import PolicyDecision

AgentStatus = Literal["investigating", "paused", "completed", "failed"]
DecisionAction = Literal["call_tool", "diagnose"]


class AgentFailure(BaseModel):
    category: str
    message: str
    retryable: bool = False
    attempts: int = 1
    resolved: bool = False


class AgentToolCall(BaseModel):
    call_index: int
    tool: str
    arguments: dict[str, Any]
    start_time: datetime
    end_time: datetime
    result: dict[str, Any] | None
    success: bool
    error: str | None = None


class KnowledgeCitation(BaseModel):
    source: str
    document: str
    chunk: int
    similarity: float
    content: str


class Hypothesis(BaseModel):
    hypothesis: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0, description="Model-assigned hypothesis score; not a calibrated probability.")
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    contradicting_evidence: list[dict[str, Any]] = Field(default_factory=list)


class AgentState(BaseModel):
    run_id: UUID
    user_request: str
    service: str | None = None
    severity: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    hypothesis_history: list[list[Hypothesis]] = Field(default_factory=list)
    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    knowledge: list[KnowledgeCitation] = Field(default_factory=list)
    diagnosis: str | None = None
    proposed_action: ActionProposal | None = None
    policy_decision: PolicyDecision | None = None
    approval: ApprovalRecord | None = None
    status: AgentStatus = "investigating"
    retrieval_status: Literal["not_started", "ok", "empty", "failed"] = "not_started"
    failure_states: list[AgentFailure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    escalation_required: bool = False


class AgentDecision(BaseModel):
    action: DecisionAction
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    service: str | None = None
    severity: str | None = None
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    diagnosis: str | None = None
    proposed_action: ActionProposal | None = None


class InvestigationRequest(BaseModel):
    request: str = Field(..., min_length=1)
