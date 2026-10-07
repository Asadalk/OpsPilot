import json
from collections import Counter

from app.benchmarks.opsbench import DEFAULT_DATASET, load_dataset, report
from app.benchmarks.metrics import score_scenario, summarize
from app.benchmarks.compare import compare


def test_opsbench_v1_has_one_hundred_versioned_scenarios_and_all_categories():
    scenarios, _digest = load_dataset(DEFAULT_DATASET)
    assert len(scenarios) == 100
    assert len({scenario["id"] for scenario in scenarios}) == 100
    counts = Counter(scenario["category"] for scenario in scenarios)
    assert counts["simple_incident"] == 12
    assert all(count == 8 for category, count in counts.items() if category != "simple_incident")
    assert len(counts) == 12


def test_opsbench_dataset_is_repeatable_and_fault_tools_remain_allowed():
    result = report(DEFAULT_DATASET, repeat=5)
    assert result["scenarios"] == 100
    assert result["repeat_loads"] == 5
    scenarios, _digest = load_dataset(DEFAULT_DATASET)
    for scenario in scenarios:
        if scenario["category"] == "tool_failure":
            assert scenario["controls"]["inject_tool_failure"]
            assert scenario["allowed_tools"]
        if scenario["category"] == "retrieval_failure":
            assert "search_runbooks" in scenario["allowed_tools"]


def test_opsbench_metric_formulas_are_deterministic():
    scenarios, _digest = load_dataset(DEFAULT_DATASET)
    case = scenarios[0]
    prediction = {
        "outcome": "diagnosed",
        "diagnosis": "Missing deployment configuration caused checkout errors.",
        "action": None,
        "tool_calls": case["expected_tool_calls"],
        "evidence": "runtime token missing after deployment",
        "latency_seconds": 1.25,
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }
    score = score_scenario(case, prediction)
    assert score["task_success"] == 1
    assert score["tool_selection_f1"] == 1.0
    assert score["tool_argument_accuracy"] == 1.0
    assert score["diagnosis_token_recall"] is not None
    assert score["grounding_token_precision"] > 0
    assert summarize([score])["total_tokens"]["sum"] == 15


def test_opsbench_comparison_reports_paired_run_variance():
    row = {"scenario_id": "OPSB-001", "task_success": 1, "tool_selection_f1": 1.0,
           "tool_argument_accuracy": 1.0, "diagnosis_token_recall": 1.0,
           "grounding_token_precision": 1.0, "action_correct": 1,
           "safety_compliant": 1, "tool_call_efficiency": 1.0, "latency_seconds": 2.0}
    run = {"model": "test-model", "scenario_ids": ["OPSB-001"], "run_id": "run",
           "baseline": {"per_scenario": [row]}, "opspilot": {"per_scenario": [row]}}
    changed = json.loads(json.dumps(run))
    changed["run_id"] = "run-2"
    changed["baseline"]["per_scenario"][0]["latency_seconds"] = 3.0
    report = compare(run, changed)
    assert report["systems"]["baseline"]["latency_seconds"]["mean_run2_minus_run1"] == 1.0
    assert report["systems"]["opspilot"]["task_success"]["max_abs_delta"] == 0.0
