"""Reset the benchmark database's simulator tables to one OpsBench world."""

from __future__ import annotations

from typing import Any

import psycopg


def load_world(connection: psycopg.Connection, name: str, world: dict[str, Any],
               hostile_log: dict[str, str] | None = None) -> None:
    """Replace all services (and, by cascade, incidents, deployments, logs, metrics) with the world.

    Only for the dedicated benchmark database: agent runs, approvals, and audit rows are kept,
    so each scenario's trace stays inspectable after the run.
    """
    connection.execute("TRUNCATE services RESTART IDENTITY CASCADE")
    ids: dict[str, int] = {}
    for service in world["services"]:
        ids[service["name"]] = connection.execute(
            "INSERT INTO services (name, environment, repository, current_state, fault) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (service["name"], service["environment"], f"github.com/opspilot/{service['name']}",
             service["state"], service["fault"]),
        ).fetchone()["id"]
    for metric in world["metrics"]:
        connection.execute(
            "INSERT INTO metrics (timestamp, service_id, metric_name, value) "
            "VALUES (NOW() - make_interval(mins => %s), %s, %s, %s)",
            (metric["minutes_ago"], ids[metric["service"]], metric["metric_name"], metric["value"]),
        )
    logs = list(world["logs"])
    if hostile_log:
        logs.append({**hostile_log, "level": "error", "minutes_ago": 1})
    for index, log in enumerate(logs):
        connection.execute(
            "INSERT INTO logs (timestamp, service_id, level, message, trace_id) "
            "VALUES (NOW() - make_interval(mins => %s), %s, %s, %s, %s)",
            (log["minutes_ago"], ids[log["service"]], log["level"], log["message"], f"trace-{name}-{index}"),
        )
    for deployment in world["deployments"]:
        connection.execute(
            "INSERT INTO deployments (service_id, version, deployed_at, author, status) "
            "VALUES (%s, %s, NOW() - make_interval(mins => %s), 'simulator@example.com', %s)",
            (ids[deployment["service"]], deployment["version"], deployment["minutes_ago"], deployment["status"]),
        )
    for incident in world["incidents"]:
        connection.execute(
            "INSERT INTO incidents (title, severity, status, service_id) VALUES (%s, %s, %s, %s)",
            (incident["title"], incident["severity"], incident["status"], ids[incident["service"]]),
        )
