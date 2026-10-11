"""Flagship demo: drive the real HTTP API through one incident, then show one blocked action.

  docker compose exec backend python -m app.demo.flagship --reset

--reset replaces the simulator tables (services and everything that references them) with
the OpsBench "checkout_bad_deploy" world: checkout-api is failing after its latest release,
and an earlier good release exists. Agent runs, approvals, and audit history are kept.

The script then goes through the same endpoints the UI uses:
  operator investigates → policy requires approval → admin approves → rollback executes →
  verification → incident resolved → audit story and run timeline;
and a viewer's restart request, which policy denies. Nothing here bypasses the pipeline.
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

from app.benchmarks.opsbench import DEFAULT_DATASET, load_dataset
from app.benchmarks.worlds import load_world
from app.core.config import settings
from app.db.database import get_connection

WORLD = "checkout_bad_deploy"
REQUEST = ("Checkout failures increased after the latest deployment of checkout-api. "
           "Investigate and remediate if the evidence supports it.")


def reset_simulator() -> None:
    world = load_dataset(DEFAULT_DATASET)[0]["worlds"][WORLD]
    with get_connection(settings.database_url) as connection:
        load_world(connection, WORLD, world)


def login(client: httpx.Client, username: str, password: str) -> dict[str, str]:
    response = client.post("/auth/token", json={"username": username, "password": password})
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def show(title: str, lines: list[str]) -> None:
    print(f"\n== {title}")
    for line in lines:
        print(f"   {line}")


def flagship(client: httpx.Client, users: dict[str, tuple[str, str]]) -> bool:
    operator = login(client, *users["operator"])
    incident = next(item for item in client.get("/incidents", headers=operator).json()
                    if item["service"] == "checkout-api" and item["status"] != "resolved")
    show("Incident", [f"INC-{incident['id']:03d} {incident['title']} ({incident['severity']}, {incident['status']})"])

    run = client.post("/agent/investigate", json={"request": REQUEST}, headers=operator, timeout=300).json()
    show("Investigation (operator)", [
        *(f"tool {call['tool']}({call['arguments'].get('service', '')}) → {'ok' if call['success'] else 'failed'}"
          for call in run["tool_calls"]),
        *(f"hypothesis {item['score']:.2f}: {item['hypothesis'][:90]}" for item in run["hypotheses"]),
        f"diagnosis: {(run['diagnosis'] or '').splitlines()[0][:160]}",
        f"proposal: {run['proposed_action']['action_type']} {run['proposed_action']['target']}" if run["proposed_action"] else "proposal: none",
        f"policy: {run['policy_decision']['outcome']} (risk {run['policy_decision']['risk_level']})" if run["policy_decision"] else "policy: not evaluated",
        f"run status: {run['status']}",
    ])
    if not run.get("approval"):
        print("\nNo approval was requested; the flagship path needs a HIGH-risk proposal.")
        return False

    approval_id = run["approval"]["id"]
    self_attempt = client.post(f"/approvals/{approval_id}/approve", json={"reason": "self-approval"}, headers=operator)
    admin = login(client, *users["admin"])
    decided = client.post(f"/approvals/{approval_id}/approve", json={"reason": "Evidence reviewed; approve rollback."},
                          headers=admin).json()
    verification = decided["execution_result"]["verification"]
    show("Approval and execution", [
        f"operator approving own request → HTTP {self_attempt.status_code} ({self_attempt.json().get('detail')})",
        f"admin decision: {decided['decision']} by {decided['decided_by']}",
        f"executed: {decided['execution_result']['action_type']} on {decided['execution_result']['target']}",
        f"verification: {verification['status']} after {verification['attempt_count']} attempt(s) — {verification['reason']}",
        f"resolved incidents: {decided['execution_result']['resolved_incident_ids']}",
    ])

    story = client.get(f"/audit/incidents/{incident['id']}", headers=admin).json()
    show("Audit story", [f"{event['occurred_at'][11:19]} {event['actor']:<18} {event['event_type']}"
                         for event in story["events"]][-14:])
    events = client.get(f"/agent/runs/{run['run_id']}/events", headers=admin).json()["events"]
    show("Run timeline (agent_events)", [f"{event['event_type']:<14} {event['status']:<16} {event.get('tool') or ''}"
                                         for event in events])
    return verification["status"] == "SUCCESS" and bool(decided["execution_result"]["resolved_incident_ids"])


def blocked_action(client: httpx.Client, users: dict[str, tuple[str, str]]) -> bool:
    viewer = login(client, *users["viewer"])
    run = client.post("/agent/investigate", json={"request": "Restart checkout-api now."}, headers=viewer,
                      timeout=300).json()
    decision = run.get("policy_decision") or {}
    show("Failure demo: viewer asks for a restart", [
        f"proposal: {run['proposed_action']['action_type'] if run['proposed_action'] else 'none'}",
        f"policy: {decision.get('outcome', 'not evaluated')} — {decision.get('reason', '')}",
        f"approval created: {bool(run.get('approval'))}; run status: {run['status']}",
    ])
    return not run.get("approval") and decision.get("outcome") in {None, "deny"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OpsPilot flagship demo through the HTTP API")
    parser.add_argument("--reset", action="store_true", help="reset the simulator to the demo world first")
    parser.add_argument("--api", default=os.getenv("OPSPILOT_API", "http://127.0.0.1:8000"))
    args = parser.parse_args()
    users = {role: (os.getenv(f"DEMO_{role.upper()}_USER", role), os.getenv(f"DEMO_{role.upper()}_PASSWORD", role))
             for role in ("viewer", "operator", "admin")}
    if args.reset:
        reset_simulator()
        print(f"Simulator reset to the '{WORLD}' world.")
    with httpx.Client(base_url=args.api, timeout=60) as client:
        ok = flagship(client, users)
        blocked = blocked_action(client, users)
    print(f"\nFlagship flow: {'PASS' if ok else 'FAIL'}   Blocked action: {'PASS' if blocked else 'FAIL'}")
    sys.exit(0 if ok and blocked else 1)


if __name__ == "__main__":
    main()
