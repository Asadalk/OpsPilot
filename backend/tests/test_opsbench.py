from collections import Counter

from app.benchmarks.opsbench import DEFAULT_DATASET, load_dataset, report


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
