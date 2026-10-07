from datetime import datetime
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.db.database import get_connection


class AgentRepositoryError(Exception):
    pass


class AgentRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def create_run(self, run_id: UUID, user_request: str) -> None:
        try:
            with get_connection(self.database_url) as connection:
                connection.execute(
                    "INSERT INTO agent_runs (run_id, user_request, status) VALUES (%s, %s, %s)",
                    (run_id, user_request, "investigating"),
                )
        except psycopg.Error as exc:
            raise AgentRepositoryError from exc

    def record_tool_call(
        self,
        run_id: UUID,
        call_index: int,
        tool: str,
        arguments: dict,
        start_time: datetime,
        end_time: datetime,
        result: dict | None,
        success: bool,
        error: str | None,
    ) -> None:
        try:
            with get_connection(self.database_url) as connection:
                connection.execute(
                    "INSERT INTO agent_tool_calls "
                    "(run_id, call_index, tool, arguments, start_time, end_time, result, success, error) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (run_id, call_index, tool, Jsonb(arguments), start_time, end_time, Jsonb(result) if result else None, success, error),
                )
        except psycopg.Error as exc:
            raise AgentRepositoryError from exc

    def complete_run(
        self,
        run_id: UUID,
        service: str | None,
        severity: str | None,
        evidence: list[dict],
        hypotheses: list[str],
        knowledge_citations: list[dict],
        diagnosis: str | None,
        proposed_action: str | None,
        status: str,
    ) -> None:
        try:
            with get_connection(self.database_url) as connection:
                connection.execute(
                    "UPDATE agent_runs SET service = %s, severity = %s, evidence = %s, hypotheses = %s, "
                    "knowledge_citations = %s, diagnosis = %s, proposed_action = %s, status = %s, completed_at = NOW() WHERE run_id = %s",
                    (service, severity, Jsonb(evidence), Jsonb(hypotheses), Jsonb(knowledge_citations), diagnosis, proposed_action, status, run_id),
                )
        except psycopg.Error as exc:
            raise AgentRepositoryError from exc