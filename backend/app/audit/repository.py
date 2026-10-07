from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.audit.schemas import AuditedIncident, AuditEvent, IncidentAuditStory
from app.db.database import get_connection


def append_audit_event(
    connection: psycopg.Connection,
    *,
    actor: str,
    event_type: str,
    entity_type: str,
    entity_id: str | int | None = None,
    run_id: UUID | None = None,
    reason: str | None = None,
    result: dict | None = None,
    details: dict | None = None,
) -> None:
    connection.execute(
        "INSERT INTO audit_events (actor, event_type, entity_type, entity_id, run_id, reason, result, details) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (actor, event_type, entity_type, str(entity_id) if entity_id is not None else None,
         run_id, reason, Jsonb(result or {}), Jsonb(details or {})),
    )


class AuditRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def record(self, **event: Any) -> None:
        with get_connection(self.database_url) as connection:
            append_audit_event(connection, **event)

    def incident_story(self, incident_id: int) -> IncidentAuditStory | None:
        with get_connection(self.database_url) as connection:
            incident = connection.execute(
                "SELECT i.id, i.title, i.severity, i.status, s.name AS service "
                "FROM incidents i JOIN services s ON s.id = i.service_id WHERE i.id = %s", (incident_id,)
            ).fetchone()
            if incident is None:
                return None
            events = connection.execute(
                "SELECT event_id, occurred_at, actor, event_type, entity_type, entity_id, run_id, reason, result, details "
                "FROM audit_events WHERE (entity_type = 'incident' AND entity_id = %s) OR run_id IN ("
                "SELECT run_id FROM audit_events WHERE entity_type = 'incident' AND entity_id = %s AND event_type = 'incident.investigation_linked') "
                "ORDER BY occurred_at, event_id", (str(incident_id), str(incident_id))
            ).fetchall()
        return IncidentAuditStory(
            incident=AuditedIncident(**incident),
            events=[AuditEvent.model_validate(row) for row in events],
        )
