from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


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
    started_at: datetime
    completed_at: datetime | None
    events: list[AgentEvent]
