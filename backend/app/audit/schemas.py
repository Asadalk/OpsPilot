from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditEvent(BaseModel):
    event_id: int
    occurred_at: datetime
    actor: str
    event_type: str
    entity_type: str
    entity_id: str | None
    run_id: UUID | None
    reason: str | None
    result: dict[str, Any]
    details: dict[str, Any]


class AuditedIncident(BaseModel):
    id: int
    title: str
    severity: str
    status: str
    service: str


class IncidentAuditStory(BaseModel):
    incident: AuditedIncident
    events: list[AuditEvent]
