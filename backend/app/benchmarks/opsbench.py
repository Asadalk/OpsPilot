"""Load and validate OpsBench datasets without calling an LLM or mutating OpsPilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = BACKEND_ROOT / "benchmarks" / "opsbench" / "v1" / "scenarios.json"
VALID_CATEGORIES = {
    "simple_incident", "multi_step_incident", "ambiguous_incident", "misleading_evidence",
    "missing_information", "tool_failure", "retrieval_failure", "dangerous_request",
    "permission_violation", "prompt_injection", "approval_rejection", "verification_failure",
}
VALID_TOOLS = {
    "get_service_health", "get_metrics", "search_logs", "get_recent_deployments",
    "get_incident_history", "search_runbooks",
}
VALID_ACTIONS = {
    None, "create_incident", "update_incident", "create_github_issue", "generate_report",
    "restart_service", "rollback_deployment", "delete_data",
}
VALID_OUTCOMES = {
    "diagnosed", "uncertain", "escalated", "denied", "approval_required", "rejected", "verification_failed",
}
REQUIRED_FIELDS = {
    "id", "category", "input", "service", "expected_root_cause", "allowed_tools",
    "expected_action", "approval_required", "expected_outcome", "controls",
}


class OpsBenchValidationError(ValueError):
    pass


def load_dataset(path: Path = DEFAULT_DATASET) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpsBenchValidationError(f"invalid JSON: {exc}") from exc
    if payload.get("name") != "OpsBench" or payload.get("version") != "1.0.0":
        raise OpsBenchValidationError("dataset name/version must be OpsBench/1.0.0")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise OpsBenchValidationError("dataset must contain a non-empty scenarios array")
    seen: set[str] = set()
    for index, scenario in enumerate(scenarios):
        missing = REQUIRED_FIELDS - scenario.keys()
        if missing:
            raise OpsBenchValidationError(f"scenario {index} missing fields: {sorted(missing)}")
        scenario_id = scenario["id"]
        if not isinstance(scenario_id, str) or not scenario_id.startswith("OPSB-") or scenario_id in seen:
            raise OpsBenchValidationError(f"scenario {index} has invalid or duplicate id: {scenario_id!r}")
        seen.add(scenario_id)
        if scenario["category"] not in VALID_CATEGORIES:
            raise OpsBenchValidationError(f"{scenario_id}: unknown category {scenario['category']!r}")
        if not scenario["input"].strip() or not scenario["service"].strip():
            raise OpsBenchValidationError(f"{scenario_id}: input and service are required")
        if not isinstance(scenario["allowed_tools"], list) or not set(scenario["allowed_tools"]) <= VALID_TOOLS:
            raise OpsBenchValidationError(f"{scenario_id}: allowed_tools contains an unknown tool")
        if scenario["expected_action"] not in VALID_ACTIONS:
            raise OpsBenchValidationError(f"{scenario_id}: unknown expected_action")
        if not isinstance(scenario["approval_required"], bool):
            raise OpsBenchValidationError(f"{scenario_id}: approval_required must be boolean")
        if scenario["expected_outcome"] == "approval_required" and not scenario["approval_required"]:
            raise OpsBenchValidationError(f"{scenario_id}: approval_required outcome must set approval_required=true")
        if scenario["category"] in {"approval_rejection", "verification_failure"} and not scenario["approval_required"]:
            raise OpsBenchValidationError(f"{scenario_id}: category requires a high-risk action approval")
        if scenario["expected_outcome"] not in VALID_OUTCOMES:
            raise OpsBenchValidationError(f"{scenario_id}: unknown expected_outcome")
        if not isinstance(scenario["controls"], dict):
            raise OpsBenchValidationError(f"{scenario_id}: controls must be an object")
    missing_categories = VALID_CATEGORIES - {scenario["category"] for scenario in scenarios}
    if missing_categories:
        raise OpsBenchValidationError(f"dataset missing categories: {sorted(missing_categories)}")
    return scenarios, hashlib.sha256(raw).hexdigest()


def report(path: Path = DEFAULT_DATASET, repeat: int = 1) -> dict[str, Any]:
    if repeat < 1:
        raise OpsBenchValidationError("repeat must be at least 1")
    first_digest = ""
    counts: Counter[str] = Counter()
    for run in range(repeat):
        scenarios, digest = load_dataset(path)
        counts = Counter(item["category"] for item in scenarios)
        if run and digest != first_digest:
            raise OpsBenchValidationError("dataset content changed between repeated loads")
        first_digest = digest
    return {
        "dataset": "OpsBench",
        "version": "1.0.0",
        "scenarios": sum(counts.values()),
        "repeat_loads": repeat,
        "sha256": first_digest,
        "category_counts": dict(sorted(counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and repeatably load OpsBench v1 scenarios")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    try:
        print(json.dumps(report(args.dataset, args.repeat), indent=2))
    except (OSError, OpsBenchValidationError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
