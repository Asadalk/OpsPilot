from typing import Any
from uuid import uuid4

import psycopg

from app.actions.schemas import ActionProposal, SimulatorActionResult, SimulatorSnapshot

MAX_AUTOMATIC_ATTEMPTS = 2


class SimulatorActionRepository:
    """Apply and verify an approved action inside the caller's DB transaction."""

    def execute(self, connection: psycopg.Connection, proposal: ActionProposal) -> dict[str, Any]:
        service_name = proposal.target.split("@", 1)[0]
        service = connection.execute(
            "SELECT id, name, current_state FROM services WHERE name = %s FOR UPDATE",
            (service_name,),
        ).fetchone()
        if service is None:
            return self._result(proposal, [], "FAILED", f"Unknown simulator service: {service_name}")

        attempts: list[dict[str, Any]] = []
        final_reason = "Action did not produce a verifiable improvement."
        verification_status = "INCONCLUSIVE"
        for attempt_number in range(1, MAX_AUTOMATIC_ATTEMPTS + 1):
            before = self._snapshot(connection, service["id"])
            execution = self._apply(connection, proposal, service["id"], before)
            after = self._snapshot(connection, service["id"])
            verification_status, final_reason = self._verify(before, after, execution)
            attempt = {
                "attempt": attempt_number,
                "before": before,
                "execution": execution,
                "after": after,
                "verification": verification_status,
                "reason": final_reason,
            }
            if verification_status == "SUCCESS":
                attempts.append(attempt)
                break
            if verification_status == "FAILED" and attempt_number < MAX_AUTOMATIC_ATTEMPTS:
                # The retry is based on a fresh deterministic health and metric read.
                attempt["reinvestigation"] = self._snapshot(connection, service["id"])
                attempts.append(attempt)
                continue
            attempts.append(attempt)
            break

        resolved_incidents: list[int] = []
        if verification_status == "SUCCESS":
            rows = connection.execute(
                "UPDATE incidents SET status = 'resolved', updated_at = NOW() "
                "WHERE service_id = %s AND status IN ('open', 'investigating') RETURNING id",
                (service["id"],),
            ).fetchall()
            resolved_incidents = [row["id"] for row in rows]

        return SimulatorActionResult.model_validate({
            "status": "simulated",
            "action_type": proposal.action_type,
            "target": service_name,
            "pre_action_state": attempts[0]["before"] if attempts else None,
            "post_action_state": attempts[-1]["after"] if attempts else None,
            "verification": {
                "status": verification_status,
                "reason": final_reason,
                "attempt_count": len(attempts),
                "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
                "escalated": verification_status != "SUCCESS",
                "attempts": attempts,
            },
            "resolved_incident_ids": resolved_incidents,
            "message": "No real infrastructure was changed.",
        }).model_dump(mode="json")

    @staticmethod
    def _snapshot(connection: psycopg.Connection, service_id: int) -> dict[str, Any]:
        service = connection.execute(
            "SELECT name, current_state FROM services WHERE id = %s", (service_id,)
        ).fetchone()
        metrics = connection.execute(
            "SELECT DISTINCT ON (metric_name) metric_name, value FROM metrics "
            "WHERE service_id = %s ORDER BY metric_name, timestamp DESC, id DESC",
            (service_id,),
        ).fetchall()
        deployment = connection.execute(
            "SELECT version, status FROM deployments WHERE service_id = %s "
            "ORDER BY deployed_at DESC, deployment_id DESC LIMIT 1",
            (service_id,),
        ).fetchone()
        return SimulatorSnapshot.model_validate({
            "service": service["name"],
            "state": service["current_state"],
            "metrics": {row["metric_name"]: row["value"] for row in metrics},
            "latest_deployment": dict(deployment) if deployment else None,
        }).model_dump(mode="json")

    def _apply(self, connection: psycopg.Connection, proposal: ActionProposal, service_id: int, before: dict) -> dict[str, Any]:
        if proposal.action_type == "restart_service":
            connection.execute("UPDATE services SET current_state = 'healthy' WHERE id = %s", (service_id,))
            self._lower_metrics(connection, service_id, before["metrics"])
            self._record_log(connection, service_id, "Simulated restart completed.")
            return {"applied": True, "operation": "restart_service"}

        if proposal.action_type == "rollback_deployment":
            deployments = connection.execute(
                "SELECT deployment_id, version, status, deployed_at FROM deployments "
                "WHERE service_id = %s AND status != 'rolled_back' "
                "ORDER BY deployed_at DESC, deployment_id DESC",
                (service_id,),
            ).fetchall()
            current = deployments[0] if deployments else None
            previous_success = next(
                (row for row in deployments[1:] if row["status"] == "success"), None
            )
            if current is None or previous_success is None:
                return {
                    "applied": False,
                    "operation": "rollback_deployment",
                    "reason": "No earlier successful deployment is available to roll back to.",
                }
            connection.execute(
                "UPDATE deployments SET status = 'rolled_back' WHERE deployment_id = %s",
                (current["deployment_id"],),
            )
            connection.execute("UPDATE services SET current_state = 'healthy' WHERE id = %s", (service_id,))
            self._lower_metrics(connection, service_id, before["metrics"])
            self._record_log(connection, service_id, f"Simulated rollback to {previous_success['version']} completed.")
            return {
                "applied": True,
                "operation": "rollback_deployment",
                "rolled_back_version": current["version"],
                "restored_version": previous_success["version"],
            }

        return {"applied": False, "operation": proposal.action_type, "reason": "Action is not supported by the simulator."}

    @staticmethod
    def _lower_metrics(connection: psycopg.Connection, service_id: int, metrics: dict[str, float]) -> None:
        for metric_name, value in metrics.items():
            normalized_name = metric_name.lower()
            if not any(marker in normalized_name for marker in ("latency", "error", "rate", "queue", "backlog", "depth", "timeout")):
                continue
            lowered = round(max(0.0, value * 0.25), 4)
            connection.execute(
                "INSERT INTO metrics (timestamp, service_id, metric_name, value) VALUES (NOW(), %s, %s, %s)",
                (service_id, metric_name, lowered),
            )

    @staticmethod
    def _record_log(connection: psycopg.Connection, service_id: int, message: str) -> None:
        connection.execute(
            "INSERT INTO logs (timestamp, service_id, level, message, trace_id) VALUES (NOW(), %s, 'info', %s, %s)",
            (service_id, message, f"sim-action-{uuid4()}"),
        )

    @staticmethod
    def _verify(before: dict, after: dict, execution: dict) -> tuple[str, str]:
        if not execution.get("applied"):
            return "FAILED", execution.get("reason", "The simulator action was not applied.")
        if after["state"] != "healthy":
            return "FAILED", f"Service state remains {after['state']} after execution."
        improved = any(
            name in before["metrics"] and value < before["metrics"][name]
            for name, value in after["metrics"].items()
        )
        if before["state"] != "healthy" or improved:
            return "SUCCESS", "Service health or recorded metrics improved after the action."
        return "INCONCLUSIVE", "The service was already healthy and no metric evidence was available to confirm improvement."

    @staticmethod
    def _result(proposal: ActionProposal, attempts: list[dict], status: str, reason: str) -> dict[str, Any]:
        return SimulatorActionResult.model_validate({
            "status": "simulated",
            "action_type": proposal.action_type,
            "target": proposal.target,
            "pre_action_state": None,
            "post_action_state": None,
            "verification": {
                "status": status,
                "reason": reason,
                "attempt_count": len(attempts),
                "max_automatic_attempts": MAX_AUTOMATIC_ATTEMPTS,
                "escalated": True,
                "attempts": attempts,
            },
            "resolved_incident_ids": [],
            "message": "No real infrastructure was changed.",
        }).model_dump(mode="json")
