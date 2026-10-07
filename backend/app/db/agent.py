from datetime import datetime
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.audit.repository import append_audit_event
from app.db.database import get_connection
from app.db.agent_events import append_agent_event


class AgentRepositoryError(Exception):
    pass


class AgentRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def create_run(self, run_id: UUID, user_request: str, actor: str = "system") -> None:
        try:
            with get_connection(self.database_url) as connection:
                connection.execute(
                    "INSERT INTO agent_runs (run_id, user_request, status) VALUES (%s, %s, %s)",
                    (run_id, user_request, "investigating"),
                )
                append_audit_event(connection, actor=actor, event_type="agent.started", entity_type="run",
                                   entity_id=run_id, run_id=run_id, reason=user_request,
                                   result={"status": "investigating"})
                append_agent_event(connection, run_id=run_id, event_type="run.started", status="started",
                                   details={"actor": actor})
        except psycopg.Error as exc:
            raise AgentRepositoryError from exc

    def record_event(self, run_id: UUID, event_type: str, status: str, *,
                     duration_ms: int | None = None, model: str | None = None,
                     tool: str | None = None, error: str | None = None,
                     details: dict | None = None) -> None:
        try:
            with get_connection(self.database_url) as connection:
                append_agent_event(connection, run_id=run_id, event_type=event_type,
                                   status=status, duration_ms=duration_ms, model=model,
                                   tool=tool, error=error, details=details)
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
        actor: str = "system",
    ) -> None:
        try:
            with get_connection(self.database_url) as connection:
                connection.execute(
                    "INSERT INTO agent_tool_calls "
                    "(run_id, call_index, tool, arguments, start_time, end_time, result, success, error) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (run_id, call_index, tool, Jsonb(arguments), start_time, end_time, Jsonb(result) if result else None, success, error),
                )
                append_audit_event(connection, actor=actor,
                                   event_type="tool.called" if success else "tool.failed",
                                   entity_type="run", entity_id=run_id, run_id=run_id,
                                   reason=error, result={"success": success, "error": error},
                                   details={"call_index": call_index, "tool": tool,
                                            "arguments": arguments, "started_at": start_time.isoformat(),
                                            "finished_at": end_time.isoformat(), "result": result})
                stage = {
                    "get_service_health": "health",
                    "get_metrics": "metrics",
                    "search_logs": "logs",
                    "get_recent_deployments": "deployment",
                    "get_incident_history": "incident_history",
                    "search_runbooks": "runbook_search",
                }.get(tool, "tool")
                append_agent_event(
                    connection, run_id=run_id, event_type=stage,
                    duration_ms=max(0, int((end_time - start_time).total_seconds() * 1000)),
                    tool=tool, status="completed" if success else "failed", error=error,
                    details={"call_index": call_index, "arguments": arguments, "result": result},
                )
        except psycopg.Error as exc:
            raise AgentRepositoryError from exc

    def complete_run(
        self,
        run_id: UUID,
        service: str | None,
        severity: str | None,
        evidence: list[dict],
        hypotheses: list[dict],
        hypothesis_history: list[list[dict]],
        knowledge_citations: list[dict],
        action_proposal: dict | None,
        policy_decision: dict | None,
        diagnosis: str | None,
        proposed_action: str | None,
        status: str,
        actor: str = "system",
        audit_action: bool = True,
    ) -> None:
        try:
            with get_connection(self.database_url) as connection:
                connection.execute(
                    "UPDATE agent_runs SET service = %s, severity = %s, evidence = %s, hypotheses = %s, "
                    "knowledge_citations = %s, hypothesis_history = %s, action_proposal = %s, policy_decision = %s, diagnosis = %s, proposed_action = %s, status = %s, completed_at = CASE WHEN %s = 'paused' THEN NULL ELSE NOW() END WHERE run_id = %s",
                    (service, severity, Jsonb(evidence), Jsonb(hypotheses), Jsonb(hypothesis_history), Jsonb(knowledge_citations), Jsonb(action_proposal) if action_proposal else None, Jsonb(policy_decision) if policy_decision else None, diagnosis, action_proposal["reason"] if action_proposal else None, status, status, run_id),
                )
                if audit_action and action_proposal:
                    append_audit_event(connection, actor=actor, event_type="action.proposed", entity_type="run",
                                       entity_id=run_id, run_id=run_id, reason=action_proposal.get("reason"),
                                       result={"status": action_proposal.get("status")}, details=action_proposal)
                    append_audit_event(connection, actor=actor, event_type="policy.evaluated", entity_type="run",
                                       entity_id=run_id, run_id=run_id,
                                       result=policy_decision or {}, details={"action_type": action_proposal.get("action_type")})
                if service:
                    incidents = connection.execute(
                        "SELECT i.id, i.title FROM incidents i JOIN services s ON s.id=i.service_id "
                        "WHERE s.name=%s AND i.status IN ('open','investigating')", (service,)
                    ).fetchall()
                    for incident in incidents:
                        append_audit_event(connection, actor=actor, event_type="incident.investigation_linked",
                                           entity_type="incident", entity_id=incident["id"], run_id=run_id,
                                           reason="Agent investigated the incident service.",
                                           result={"status": status}, details={"run_id": str(run_id), "service": service})
                append_audit_event(connection, actor=actor,
                                   event_type={"paused": "agent.paused", "failed": "agent.failed"}.get(status, "agent.completed"),
                                   entity_type="run", entity_id=run_id, run_id=run_id,
                                   reason=diagnosis, result={"status": status},
                                   details={"service": service, "severity": severity})
                append_agent_event(connection, run_id=run_id,
                                   event_type="run.paused" if status == "paused" else "run.completed",
                                   status=status,
                                   details={"service": service, "severity": severity,
                                            "diagnosis": diagnosis})
        except psycopg.Error as exc:
            raise AgentRepositoryError from exc
