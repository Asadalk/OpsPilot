from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    event_id: int
    run_id: UUID
    event_type: str
    timestamp: datetime
    duration_ms: int | None = None
    model: str | None = None
    tool: str | None = None
    status: str
    error: str | None = None
    details: dict[str, Any]


class AgentRunTrace(BaseModel):
    run_id: UUID
    status: str
    service: str | None
    diagnosis: str | None
    user_request: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    hypothesis_history: list[list[dict[str, Any]]] = Field(default_factory=list)
    knowledge_citations: list[dict[str, Any]] = Field(default_factory=list)
    action_proposal: dict[str, Any] | None = None
    policy_decision: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime | None
    events: list[AgentEvent]
