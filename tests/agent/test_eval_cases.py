import json
from pathlib import Path

from evals.agent.runner import run

CASES = Path(__file__).parents[2] / "evals/agent/cases.json"


def test_golden_dataset_is_versioned_and_complete():
    dataset = json.loads(CASES.read_text())
    required = {"case_id","question","expected_status","expected_tool_sequence","maximum_provider_calls","required_evidence_sources","forbidden_tools","required_policy_codes"}
    assert dataset["version"] == 1 and len(dataset["cases"]) >= 12
    assert all(required <= set(case) for case in dataset["cases"])
    assert len({case["case_id"] for case in dataset["cases"]}) == len(dataset["cases"])


def test_deterministic_evaluation_suite_passes():
    report = run(CASES)
    assert report["passed"], [item for item in report["results"] if not item["passed"]]
