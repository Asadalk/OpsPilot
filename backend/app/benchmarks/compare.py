"""Compare two paired OpsBench evaluation artifacts without hiding variance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


METRICS = (
    "task_success", "tool_selection_f1", "tool_argument_accuracy", "diagnosis_token_recall",
    "grounding_token_precision", "action_correct", "safety_compliant", "tool_call_efficiency",
    "latency_seconds",
)


def compare(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    if first.get("model") != second.get("model") or first.get("scenario_ids") != second.get("scenario_ids"):
        raise ValueError("comparison requires the same model and ordered scenario IDs")
    report: dict[str, Any] = {
        "model": first["model"],
        "scenario_ids": first["scenario_ids"],
        "run_ids": [first.get("run_id"), second.get("run_id")],
        "systems": {},
    }
    for system in ("baseline", "opspilot"):
        left = {row["scenario_id"]: row for row in first[system]["per_scenario"]}
        right = {row["scenario_id"]: row for row in second[system]["per_scenario"]}
        system_deltas = {}
        for metric in METRICS:
            deltas = [right[key][metric] - left[key][metric]
                      for key in first["scenario_ids"]
                      if left[key].get(metric) is not None and right[key].get(metric) is not None]
            system_deltas[metric] = {
                "paired_n": len(deltas),
                "mean_run2_minus_run1": mean(deltas) if deltas else None,
                "population_sd": pstdev(deltas) if len(deltas) > 1 else (0.0 if deltas else None),
                "max_abs_delta": max((abs(value) for value in deltas), default=None),
            }
        report["systems"][system] = system_deltas
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare paired OpsBench runs and expose run variance")
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare(json.loads(args.first.read_text()), json.loads(args.second.read_text()))
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
