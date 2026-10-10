"""Load and validate the OpsBench v2 dataset without calling a model or touching a database."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, get_args

from app.actions.schemas import ActionType

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = BACKEND_ROOT / "benchmarks" / "opsbench" / "v2" / "scenarios.json"
CATEGORIES = {
    "simple_incident", "multi_step_incident", "ambiguous_incident", "misleading_evidence",
    "missing_information", "tool_failure", "retrieval_failure", "dangerous_request",
    "permission_violation", "prompt_injection", "approval_rejection", "verification_failure",
}
OUTCOMES = {"resolved", "verification_failed", "rejected", "approval_required", "denied", "diagnosed", "uncertain"}
READ_TOOLS = {"get_service_health", "get_metrics", "search_logs", "get_recent_deployments",
              "get_incident_history", "search_runbooks"}
CONTROLS = {"inject_tool_failure", "inject_retrieval_failure", "hostile_log", "hostile_knowledge", "approval_decision"}
ROLES = {"viewer", "operator", "admin"}


class OpsBenchValidationError(ValueError):
    pass


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise OpsBenchValidationError(message)


def load_dataset(path: Path = DEFAULT_DATASET) -> tuple[dict[str, Any], str]:
    """Return the validated dataset and the SHA-256 of its exact bytes."""
    raw = path.read_bytes()
    try:
        dataset = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpsBenchValidationError(f"invalid JSON: {exc}") from exc
    _check(dataset.get("name") == "OpsBench" and dataset.get("version") == "2.0.0", "expected OpsBench 2.0.0")
    worlds, scenarios = dataset.get("worlds", {}), dataset.get("scenarios", [])
    _check(bool(worlds) and bool(scenarios), "dataset needs worlds and scenarios")
    action_types = set(get_args(ActionType))
    seen: set[str] = set()
    for scenario in scenarios:
        sid = scenario.get("id")
        _check(isinstance(sid, str) and sid not in seen, f"invalid or duplicate id {sid!r}")
        seen.add(sid)
        _check(scenario.get("category") in CATEGORIES, f"{sid}: unknown category")
        world = worlds.get(scenario.get("world"))
        _check(world is not None, f"{sid}: unknown world")
        _check(scenario.get("role") in ROLES, f"{sid}: unknown role")
        _check(set(scenario.get("controls", {})) <= CONTROLS, f"{sid}: unknown control")
        tool = scenario["controls"].get("inject_tool_failure")
        _check(tool is None or tool in READ_TOOLS, f"{sid}: unknown injected tool")
        expected = scenario.get("expected", {})
        _check(bool(expected.get("acceptable_outcomes")) and set(expected["acceptable_outcomes"]) <= OUTCOMES,
               f"{sid}: invalid acceptable outcomes")
        for action in expected.get("acceptable_actions", []):
            _check(action is None or (len(action) == 2 and action[0] in action_types), f"{sid}: invalid action {action}")
        _check(set(expected.get("required_tools", [])) <= READ_TOOLS, f"{sid}: unknown required tool")
        leaked = [anchor for anchor in world["anchors"] if anchor in scenario["input"].lower()]
        _check(not leaked, f"{sid}: input contains evidence anchors {leaked}")
    _check(set(Counter(item["category"] for item in scenarios)) == CATEGORIES, "every category needs scenarios")
    return dataset, hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate OpsBench v2 and confirm repeated loads are identical")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    digests = set()
    for _ in range(args.repeat):
        dataset, digest = load_dataset(args.dataset)
        digests.add(digest)
    counts = Counter(item["category"] for item in dataset["scenarios"])
    print(json.dumps({"version": dataset["version"], "scenarios": len(dataset["scenarios"]),
                      "worlds": len(dataset["worlds"]), "categories": dict(sorted(counts.items())),
                      "sha256": sorted(digests), "stable": len(digests) == 1}, indent=2))


if __name__ == "__main__":
    main()
