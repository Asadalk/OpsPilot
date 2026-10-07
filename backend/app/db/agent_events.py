from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.agent.events import AgentRunTrace
from app.auth.schemas import UserPrincipal
from app.db.database import get_connection


def append_agent_event(
    connection: psycopg.Connection,
    *,
    run_id: UUID,
    event_type: str,
    status: str,
    duration_ms: int | None = None,
    model: str | None = None,
    tool: str | None = None,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        "INSERT INTO agent_events (run_id, event_type, duration_ms, model, tool, status, error, details) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (run_id, event_type, duration_ms, model, tool, status, error, Jsonb(details or {})),
    )


class AgentEventRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def for_run(self, run_id: UUID, principal: UserPrincipal) -> AgentRunTrace | None:
        with get_connection(self.database_url) as connection:
            run = connection.execute(
                "SELECT r.run_id, r.status, r.service, r.diagnosis, r.created_at AS started_at, r.completed_at "
                "FROM agent_runs r WHERE r.run_id = %s AND (" 
                "%s IN ('operator', 'admin') OR EXISTS ("
                "SELECT 1 FROM audit_events a WHERE a.run_id = r.run_id "
                "AND a.event_type = 'agent.started' AND a.actor = %s))",
                (run_id, principal.role, principal.username),
            ).fetchone()
            if run is None:
                return None
            events = connection.execute(
                "SELECT event_id, run_id, event_type, occurred_at AS timestamp, duration_ms, model, tool, "
                "status, error, details FROM agent_events WHERE run_id = %s "
                "ORDER BY occurred_at, event_id", (run_id,),
            ).fetchall()
        return AgentRunTrace.model_validate({**run, "events": events})
