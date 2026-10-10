"""Deterministic component ablations over existing OpsPilot data and simulator."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.actions.schemas import ActionProposal
from app.auth.schemas import UserPrincipal
from app.core.config import settings
from app.db.database import get_connection
from app.db.simulator_actions import SimulatorActionRepository
from app.policy.engine import PolicyEngine
from app.rag.ingest import ingest_directory
from app.rag.repository import KnowledgeRepository
from app.tools.registry import build_default_tools


KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "knowledge"
RETRIEVAL_QUERIES = [
    ("What should I check when payments latency rises?", "runbooks/payment-latency.md"),
    ("How do I investigate a payment latency spike?", "runbooks/payment-latency.md"),
    ("What evidence correlates database timeouts with latency?", "runbooks/database-timeout.md"),
    ("How should a database timeout be escalated?", "runbooks/database-timeout.md"),
    ("When is a deployment rollback considered?", "runbooks/deployment-rollback.md"),
    ("What must be approved before rollback?", "runbooks/deployment-rollback.md"),
    ("What does degraded service health mean?", "runbooks/service-health.md"),
    ("Why pair health with metrics and logs?", "runbooks/service-health.md"),
    ("What caused the checkout 500 spike?", "postmortems/checkout-configuration-mismatch.md"),
    ("How do I investigate a PAYMENT_GATEWAY_URL mismatch?", "postmortems/checkout-configuration-mismatch.md"),
    ("What evidence indicates a checkout configuration problem?", "postmortems/checkout-configuration-mismatch.md"),
    ("What caused notification provider failures?", "postmortems/notification-dependency-failure.md"),
    ("How diagnose notification connection refused errors?", "postmortems/notification-dependency-failure.md"),
    ("What evidence identifies the notification dependency?", "postmortems/notification-dependency-failure.md"),
    ("What does the payments database pool affect?", "architecture/payments-dependency-boundary.md"),
    ("How should payment trace ids be correlated?", "architecture/payments-dependency-boundary.md"),
    ("Why are database timeout and latency stronger evidence together?", "architecture/payments-dependency-boundary.md"),
    ("What should be recorded for a database timeout?", "runbooks/database-timeout.md"),
    ("What is the safe response to a failed deployment?", "runbooks/deployment-rollback.md"),
    ("How do I verify a production deployment?", "runbooks/deployment-rollback.md"),
]
SERVICES = ["payments-api", "checkout-api", "auth-api", "inventory-api", "notification-api"]
READ_TOOLS = ["get_service_health", "get_metrics", "search_logs", "get_recent_deployments", "get_incident_history"]


def _rag_ablation(database_url: str) -> dict[str, Any]:
    ingest_directory(KNOWLEDGE_DIR, database_url)
    repository = KnowledgeRepository(database_url)
    hits = 0
    first_hits = 0
    returned = 0
    for query, source in RETRIEVAL_QUERIES:
        rows = repository.search(query, top_k=3, mode="hybrid")
        sources = [row["source"] for row in rows]
        hits += source in sources
        first_hits += bool(sources and sources[0] == source)
        returned += bool(sources)
    n = len(RETRIEVAL_QUERIES)
    no_rag = {"source_recall_at_3": 0.0, "source_accuracy_at_1": 0.0, "queries_returning_documents": 0}
    with_rag = {"source_recall_at_3": hits / n, "source_accuracy_at_1": first_hits / n, "queries_returning_documents": returned}
    return _comparison("RAG", "20 fixed questions with labeled source", n, no_rag, with_rag,
                       "RAG changes the measured source retrieval rate; this does not establish diagnosis or resolution quality.",
                       "retrieval disabled", "hybrid PostgreSQL/pgvector and keyword retrieval")


def _tool_and_history_ablation(database_url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    tools = build_default_tools(database_url)
    planned_observations = 0
    planned_nonempty = 0
    history_records = 0
    calls = 0
    for service in SERVICES:
        for name in READ_TOOLS:
            tool = tools[name]
            args = {"service": service}
            if name == "search_logs":
                args["limit"] = 20
            if name in {"get_metrics", "get_recent_deployments", "get_incident_history"}:
                args["limit"] = 20
            result = tool.run(args).model_dump(mode="json")
            calls += 1
            planned_observations += 1
            collections = [value for value in result.values() if isinstance(value, list)]
            has_items = any(collection for collection in collections)
            planned_nonempty += bool(has_items or name == "get_service_health")
            if name == "get_incident_history":
                history_records += len(result.get("incidents", []))

    plan = {"read_tool_calls": calls, "nonempty_observations": planned_nonempty,
            "evidence_dimensions_queried": len(READ_TOOLS)}
    no_plan = {"read_tool_calls": 0, "nonempty_observations": 0, "evidence_dimensions_queried": 0}
    planning = _comparison("Tool planning", "5 named services; fixed five-read-tool plan", len(SERVICES), no_plan, plan,
                           "The scripted plan adds observable read evidence at the cost of additional calls; it does not measure model tool-choice accuracy.",
                           "diagnose immediately; no tool calls", "scripted deterministic read-tool sequence")

    history = _comparison("Incident history", "same five services as the tool-plan study", len(SERVICES),
                          {"history_calls": 0, "incident_records_observed": 0},
                          {"history_calls": len(SERVICES), "incident_records_observed": history_records},
                          "History supplies existing incident records for these services; this measures evidence availability, not causal diagnosis.",
                          "get_incident_history disabled", "get_incident_history called once per service")
    return planning, history


def _verification_ablation(database_url: str) -> dict[str, Any]:
    repository = SimulatorActionRepository()
    proposal = ActionProposal(action_type="restart_service", target="ablation-healthy-no-metrics",
                              reason="Controlled verification ablation", evidence=[], risk_level="HIGH", status="proposed")
    with get_connection(database_url) as connection:
        connection.execute("SAVEPOINT ablation_verification")
        service = connection.execute(
            "INSERT INTO services(name,environment,repository,current_state) VALUES (%s,'staging','benchmark/ablation','healthy') RETURNING id",
            (proposal.target,),
        ).fetchone()
        before = repository._snapshot(connection, service["id"])
        execution = repository._apply(connection, proposal, service["id"], before)
        no_verification_claim = bool(execution.get("applied"))
        connection.execute("ROLLBACK TO SAVEPOINT ablation_verification")

        connection.execute("INSERT INTO services(name,environment,repository,current_state) VALUES (%s,'staging','benchmark/ablation','healthy') RETURNING id",
                            ("ablation-healthy-no-metrics-verified",))
        verified_proposal = proposal.model_copy(update={"target": "ablation-healthy-no-metrics-verified"})
        verified = repository.execute(connection, verified_proposal)
        verified_resolved = bool(verified["resolved_incident_ids"])
        verification_status = verified["verification"]["status"]
        connection.execute("ROLLBACK TO SAVEPOINT ablation_verification")
        connection.execute("RELEASE SAVEPOINT ablation_verification")
    without = {"resolved_claims_without_success_verification": int(no_verification_claim)}
    with_check = {"resolved_claims_without_success_verification": int(verified_resolved), "verification_status": verification_status}
    return _comparison("Verification", "same healthy service state with no metrics and one simulated restart", 1,
                       without, with_check,
                       "For this no-change fixture, execution acknowledgement alone would look successful; post-action verification returned INCONCLUSIVE and did not resolve an incident.",
                       "mark resolved when simulator reports applied=true", "require SUCCESS verification to resolve")


def _unsafe_if_executed(role: str, risk: str, outcome: str) -> bool:
    """Safety invariant written independently of POLICY_RULES, so the policy can fail it.

    A write is unsafe if it would run without a human gate when: a viewer requests anything
    above LOW risk, anyone requests a CRITICAL action, or an operator requests a HIGH-risk
    production action.
    """
    if outcome != "allow":
        return False
    return (role == "viewer" and risk != "LOW") or risk == "CRITICAL" or (role == "operator" and risk == "HIGH")


def _policy_ablation() -> dict[str, Any]:
    engine = PolicyEngine()
    cases = [(role, action) for role in ("viewer", "operator", "admin")
             for action in ("restart_service", "delete_data")]
    decisions = []
    for role, action in cases:
        proposal = ActionProposal(action_type=action, target="payments-api", reason="Policy ablation case",
                                  evidence=[], risk_level="LOW", status="proposed")
        decision = engine.evaluate(proposal, UserPrincipal(username=f"ablation-{role}", role=role), "production")
        decisions.append({"role": role, "action": action, "policy_outcome": decision.outcome,
                          "canonical_risk": decision.risk_level})
    # Without the engine every proposal is allowed (fail-open control).
    unsafe_without = sum(_unsafe_if_executed(d["role"], d["canonical_risk"], "allow") for d in decisions)
    unsafe_with = sum(_unsafe_if_executed(d["role"], d["canonical_risk"], d["policy_outcome"]) for d in decisions)
    return _comparison("Policy engine", "6 role/action pairs in production", len(cases),
                       {"proposed_writes_allowed_without_policy": len(cases), "unsafe_writes_allowed": unsafe_without},
                       {"unsafe_writes_allowed": unsafe_with,
                        "denied_or_approval_gated": sum(d["policy_outcome"] != "allow" for d in decisions),
                        "decisions": decisions},
                       f"The fail-open control allows all six proposals; {unsafe_without} violate the independent safety invariant "
                       f"(viewer above LOW, any CRITICAL, operator HIGH in production). With the engine, {unsafe_with} do. "
                       "Admin restart remains allowed by configured policy.",
                       "policy disabled; all writes allowed", "server PolicyEngine with role, environment and canonical risk")


def _comparison(component: str, scenario_set: str, n: int, without: dict[str, Any], with_component: dict[str, Any],
                interpretation: str, without_config: str, with_config: str) -> dict[str, Any]:
    difference = {}
    for key, value in with_component.items():
        prior = without.get(key)
        if isinstance(value, (int, float)) and isinstance(prior, (int, float)):
            difference[key] = value - prior
    return {"component": component, "experiment": scenario_set, "scenario_count": n,
            "configuration": {"without": without_config, "with": with_config},
            "metric": list(with_component), "result": {"without": without, "with": with_component},
            "difference": difference, "interpretation": interpretation}


def run(database_url: str = settings.database_url) -> dict[str, Any]:
    planning, history = _tool_and_history_ablation(database_url)
    return {
        "study": "OpsPilot Phase 20 deterministic component ablations",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_calls": 0,
        "model_key_status": "not_used",
        "limitations": [
            "These are component-level controlled checks, not end-to-end LLM quality ablations.",
            "Tool planning uses a fixed scripted read plan; measured evidence retrieval is not model planning accuracy.",
            "Grounding and diagnosis quality are not estimated by these component checks.",
            "The verification comparator explicitly represents a naive mark-resolved-on-ack control.",
            "The no-policy comparator is fail-open (allow all writes), used to quantify the policy guard boundary.",
        ],
        "comparisons": [
            _rag_ablation(database_url), planning, history, _verification_ablation(database_url), _policy_ablation(),
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines=["# OpsPilot Phase 20 — Ablation study", "",
           "Deterministic component checks; no Gemini calls. These do not measure end-to-end model quality.", "",
           "| Component | Scenario set | Metric | Without | With | Difference | Interpretation |",
           "|---|---|---|---:|---:|---:|---|"]
    for case in report["comparisons"]:
        for metric in case["difference"]:
            before=case["result"]["without"].get(metric)
            after=case["result"]["with"].get(metric)
            diff=case["difference"][metric]
            lines.append(f"| {case['component']} | {case['scenario_count']} — {case['experiment']} | {metric} | {before} | {after} | {diff:+} | {case['interpretation']} |")
    lines += ["", "## Method and limitations", ""]
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines)+"\n"


def main() -> None:
    parser=argparse.ArgumentParser(description="Run deterministic OpsPilot component ablations")
    parser.add_argument("--json",type=Path,required=True)
    parser.add_argument("--markdown",type=Path,required=True)
    args=parser.parse_args()
    result=run()
    args.json.parent.mkdir(parents=True,exist_ok=True)
    args.markdown.parent.mkdir(parents=True,exist_ok=True)
    args.json.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    args.markdown.write_text(render_markdown(result))
    print(json.dumps({"json":str(args.json),"markdown":str(args.markdown),"comparisons":len(result["comparisons"]),"model_calls":0},indent=2))


if __name__=="__main__":
    main()
