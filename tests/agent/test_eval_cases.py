import json
from pathlib import Path


def test_scope_evaluation_suite_has_bounded_supported_and_unsupported_cases():
    cases = json.loads((Path(__file__).parents[2] / "evals/agent/cases.json").read_text())

    assert 20 <= len(cases) <= 30
    assert {case["expected"] for case in cases} >= {"describe_dataset", "find_hotspots", "get_area_metrics", "compare_areas", "unsupported"}
    assert all(1 <= len(case["question"]) <= 500 for case in cases)
