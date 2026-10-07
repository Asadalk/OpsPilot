from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AgentStatus = Literal["investigating", "completed", "failed"]
DecisionAction = Literal["call_tool", "diagnose"]


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
    proposed_action: str | None = None
    status: AgentStatus = "investigating"


class AgentDecision(BaseModel):
    action: DecisionAction
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    service: str | None = None
    severity: str | None = None
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    diagnosis: str | None = None
    proposed_action: str | None = None


class InvestigationRequest(BaseModel):
    request: str = Field(..., min_length=1)