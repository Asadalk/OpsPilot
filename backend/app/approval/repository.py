from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from typing import Any, Callable, Literal
from app.actions.schemas import ActionProposal
from app.approval.schemas import ApprovalRecord
from app.db.database import get_connection


class ApprovalError(Exception):
    pass


class ApprovalNotFound(ApprovalError):
    pass


class ApprovalConflict(ApprovalError):
    pass


class ApprovalRepository:
    def __init__(self, database_url: str, timeout_minutes: int = 60):
        self.database_url = database_url
        self.timeout_minutes = timeout_minutes

    def create_pending(self, run_id: UUID, proposal: ActionProposal) -> ApprovalRecord:
        action_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.timeout_minutes)
        try:
            with get_connection(self.database_url) as connection:
                connection.execute("SELECT run_id FROM agent_runs WHERE run_id = %s FOR UPDATE", (run_id,))
                existing = connection.execute(
                    "SELECT approvals.*, actions.proposal, actions.result AS execution_result "
                    "FROM approvals JOIN actions ON actions.action_id = approvals.action_id "
                    "WHERE approvals.run_id = %s", (run_id,)
                ).fetchone()
                if existing is not None:
                    existing_proposal = ActionProposal.model_validate(existing["proposal"])
                    if existing_proposal != proposal:
                        raise ApprovalConflict("This run already has a different approval request")
                    return self._record(existing, existing_proposal, existing["execution_result"])
                connection.execute(
                    "INSERT INTO actions (action_id, run_id, proposal, status) VALUES (%s, %s, %s, %s)",
                    (action_id, run_id, Jsonb(proposal.model_dump(mode="json")), "pending_approval"),
                )
                row = connection.execute(
                    "INSERT INTO approvals (run_id, action_id, expires_at, decision) VALUES (%s, %s, %s, %s) RETURNING *",
                    (run_id, action_id, expires_at, "pending"),
                ).fetchone()
            return self._record(row, proposal, None)
        except psycopg.Error as exc:
            raise ApprovalError from exc

    def get(self, approval_id: int) -> ApprovalRecord:
        try:
            with get_connection(self.database_url) as connection:
                row = connection.execute(
                    "SELECT approvals.*, actions.proposal, actions.result AS execution_result "
                    "FROM approvals JOIN actions ON actions.action_id = approvals.action_id WHERE approvals.id = %s",
                    (approval_id,),
                ).fetchone()
            if row is None:
                raise ApprovalNotFound
            if row["decision"] == "pending" and row["expires_at"] <= datetime.now(timezone.utc):
                return self._expire(approval_id)
            return self._record(row, ActionProposal.model_validate(row["proposal"]), row["execution_result"])
        except ApprovalNotFound:
            raise
        except psycopg.Error as exc:
            raise ApprovalError from exc

    def list_pending(self) -> list[ApprovalRecord]:
        now = datetime.now(timezone.utc)
        try:
            with get_connection(self.database_url) as connection:
                connection.execute(
                    "UPDATE approvals SET decision = 'expired', decided_at = %s, reason = 'Approval expired before a human decision.' "
                    "WHERE decision = 'pending' AND expires_at <= %s",
                    (now, now),
                )
                connection.execute(
                    "UPDATE actions SET status = 'expired' WHERE status = 'pending_approval' "
                    "AND action_id IN (SELECT action_id FROM approvals WHERE decision = 'expired')"
                )
                connection.execute(
                    "UPDATE agent_runs SET status = 'completed', diagnosis = 'Approval expired; action was not executed.', completed_at = %s "
                    "WHERE status = 'paused' AND run_id IN (SELECT run_id FROM approvals WHERE decision = 'expired')",
                    (now,),
                )
                rows = connection.execute(
                    "SELECT approvals.*, actions.proposal, actions.result AS execution_result "
                    "FROM approvals JOIN actions ON actions.action_id = approvals.action_id "
                    "WHERE approvals.decision = 'pending' ORDER BY approvals.requested_at"
                ).fetchall()
            return [self._record(row, ActionProposal.model_validate(row["proposal"]), row["execution_result"]) for row in rows]
        except psycopg.Error as exc:
            raise ApprovalError from exc

    def _expire(self, approval_id: int) -> ApprovalRecord:
        now = datetime.now(timezone.utc)
        try:
            with get_connection(self.database_url) as connection:
                row = connection.execute(
                    "UPDATE approvals SET decision = 'expired', decided_at = %s, reason = 'Approval expired before a human decision.' "
                    "WHERE id = %s AND decision = 'pending' RETURNING *", (now, approval_id)
                ).fetchone()
                if row is None:
                    full = connection.execute(
                        "SELECT approvals.*, actions.proposal, actions.result AS execution_result FROM approvals "
                        "JOIN actions ON actions.action_id = approvals.action_id WHERE approvals.id = %s", (approval_id,)
                    ).fetchone()
                else:
                    connection.execute("UPDATE actions SET status = 'expired' WHERE action_id = %s", (row["action_id"],))
                    connection.execute(
                        "UPDATE agent_runs SET status = 'completed', diagnosis = 'Approval expired; action was not executed.', completed_at = %s WHERE run_id = %s AND status = 'paused'",
                        (now, row["run_id"]),
                    )
                    full = connection.execute(
                        "SELECT approvals.*, actions.proposal, actions.result AS execution_result FROM approvals "
                        "JOIN actions ON actions.action_id = approvals.action_id WHERE approvals.id = %s", (approval_id,)
                    ).fetchone()
            return self._record(full, ActionProposal.model_validate(full["proposal"]), full["execution_result"])
        except psycopg.Error as exc:
            raise ApprovalError from exc

    def decide(
        self,
        approval_id: int,
        decision: Literal["approved", "rejected"],
        username: str,
        reason: str,
        execute_action: Callable[[psycopg.Connection, ActionProposal], dict[str, Any]] | None = None,
    ) -> ApprovalRecord:
        now = datetime.now(timezone.utc)
        try:
            with get_connection(self.database_url) as connection:
                row = connection.execute(
                    "SELECT approvals.*, actions.proposal, actions.result AS execution_result "
                    "FROM approvals JOIN actions ON actions.action_id = approvals.action_id "
                    "WHERE approvals.id = %s FOR UPDATE",
                    (approval_id,),
                ).fetchone()
                if row is None:
                    raise ApprovalNotFound
                if row["decision"] != "pending":
                    raise ApprovalConflict(f"Approval already decided: {row['decision']}")
                if row["expires_at"] <= now:
                    connection.execute("UPDATE approvals SET decision = 'expired', decided_at = %s, reason = 'Approval expired before a human decision.' WHERE id = %s", (now, approval_id))
                    connection.execute("UPDATE actions SET status = 'expired' WHERE action_id = %s", (row["action_id"],))
                    connection.execute("UPDATE agent_runs SET status = 'completed', diagnosis = 'Approval expired; action was not executed.', completed_at = %s WHERE run_id = %s AND status = 'paused'", (now, row["run_id"]))
                    expired = True
                else:
                    expired = False
                if expired:
                    row["decision"] = "expired"
                    row["decided_at"] = now
                else:
                    execution_result = None
                    proposal = ActionProposal.model_validate(row["proposal"])
                    if decision == "approved":
                        if execute_action is None:
                            raise ApprovalError("An action executor is required to approve this request")
                        execution_result = execute_action(connection, proposal)
                    connection.execute(
                        "UPDATE approvals SET decision = %s, decided_at = %s, decided_by = %s, reason = %s WHERE id = %s",
                        (decision, now, username, reason, approval_id),
                    )
                    action_status = "executed" if decision == "approved" else "rejected"
                    connection.execute("UPDATE actions SET status = %s, result = %s, executed_at = %s WHERE action_id = %s", (action_status, Jsonb(execution_result) if execution_result else None, now if execution_result else None, row["action_id"]))
                    verification = execution_result.get("verification", {}).get("status") if execution_result else None
                    if decision == "approved" and verification == "SUCCESS":
                        resolved = execution_result.get("resolved_incident_ids", [])
                        diagnosis = f"Human approval granted; verification SUCCESS; resolved incidents: {resolved}."
                    elif decision == "approved":
                        diagnosis = f"Human approval granted; verification {verification}; action requires escalation."
                    else:
                        diagnosis = "Human approval rejected; action was not executed."
                    connection.execute("UPDATE agent_runs SET status = 'completed', diagnosis = %s, completed_at = %s WHERE run_id = %s AND status = 'paused'", (diagnosis, now, row["run_id"]))
                    row["decision"] = decision
                    row["decided_at"] = now
                    row["decided_by"] = username
                    row["reason"] = reason
            if expired:
                raise ApprovalConflict("Approval has expired")
            return self._record(row, ActionProposal.model_validate(row["proposal"]), execution_result)
        except (ApprovalNotFound, ApprovalConflict):
            raise
        except psycopg.Error as exc:
            raise ApprovalError from exc

    @staticmethod
    def _record(row: dict, proposal: ActionProposal, execution_result: dict | None) -> ApprovalRecord:
        return ApprovalRecord(
            id=row["id"], run_id=row["run_id"], action_id=row["action_id"], requested_at=row["requested_at"],
            expires_at=row["expires_at"], decided_at=row.get("decided_at"), decision=row["decision"],
            decided_by=row.get("decided_by"), reason=row.get("reason"), proposal=proposal,
            execution_result=execution_result,
        )
