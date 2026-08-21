from __future__ import annotations

from typing import Any

import asyncio

from apps.api.app.agent.schemas import InvestigationRequest, ToolDecision
from apps.api.app.agent.service import InvestigationService
from services.city_data_mcp.schemas import DatasetMetadata, Evidence, MapLayer, ToolEnvelope


def envelope() -> dict[str, Any]:
    dataset = DatasetMetadata(
        city="london", dataset_id="fixture", dataset_name="London Cycling", snapshot_id="s1",
        observation_start="2024-01-01", observation_end="2024-01-02", source_organisation="TfL",
        mode="cycling", h3_resolution=9, historical=True, available_metrics=["starts"],
        supported_temporal_filters=[], limitations=["Historical"], provenance_summary={},
    )
    return ToolEnvelope(
        dataset=dataset,
        results=[{"h3_cell": "892a100d2d7ffff", "value": 7, "rank": 1}],
        evidence=[Evidence(metric="starts", value=7, unit="journeys", source_aggregate="activity", h3_cells=["892a100d2d7ffff"], filters_applied={})],
        map_layers=[MapLayer(h3_cell="892a100d2d7ffff", metric="starts", value=7, rank=1)],
        limitations=["Historical"],
    ).model_dump(mode="json")


class FakeMcp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call(self, tool: str, arguments: dict) -> dict:
        self.calls.append((tool, arguments))
        if tool == "describe_dataset":
            return envelope()["dataset"]
        return envelope()


class FakeModel:
    def __init__(self, decisions: list[ToolDecision]) -> None:
        self.decisions = iter(decisions)

    async def decide(self, question: str, context: str, tool_results: list[dict]) -> ToolDecision:
        return next(self.decisions)


def test_agent_uses_mcp_and_returns_grounded_evidence() -> None:
    mcp = FakeMcp()
    service = InvestigationService(mcp_client=mcp, model=FakeModel([
        ToolDecision(kind="call_tool", tool="find_hotspots", arguments={"city": "london", "metric": "starts", "limit": 5, "time_filter": {}}),
        ToolDecision(kind="answer", answer="The top cell has 7 starts.", follow_up_suggestions=["Compare selected cells"]),
    ]))
    result = asyncio.run(service.investigate(InvestigationRequest(question="Where are cycling hotspots?")))
    assert result.status == "answered"
    assert mcp.calls[0][0] == "find_hotspots"
    assert result.evidence[0].value == 7
    assert result.map_layers[0].h3_cell == "892a100d2d7ffff"
    assert len(result.trace) == 3


def test_agent_rejects_unsupported_question_without_mcp_call() -> None:
    mcp = FakeMcp()
    service = InvestigationService(mcp_client=mcp, model=FakeModel([
        ToolDecision(kind="unsupported", answer="I cannot answer live weather questions."),
    ]))
    result = asyncio.run(service.investigate(InvestigationRequest(question="What is the weather now?")))
    assert result.status == "unsupported"
    assert not mcp.calls


def test_agent_can_answer_dataset_description_from_direct_mcp_metadata() -> None:
    mcp = FakeMcp()
    service = InvestigationService(mcp_client=mcp, model=FakeModel([
        ToolDecision(kind="call_tool", tool="describe_dataset", arguments={"city": "london"}),
        ToolDecision(kind="answer", answer="This is a historical London cycling dataset."),
    ]))
    result = asyncio.run(service.investigate(InvestigationRequest(question="What dataset powers this?")))
    assert result.status == "answered"
    assert result.dataset is not None
    assert mcp.calls[0][0] == "describe_dataset"


def test_agent_enforces_three_round_budget() -> None:
    mcp = FakeMcp()
    service = InvestigationService(mcp_client=mcp, model=FakeModel([
        ToolDecision(kind="call_tool", tool="find_hotspots", arguments={"city": "london", "metric": "starts", "limit": 1, "time_filter": {}}),
        ToolDecision(kind="call_tool", tool="find_hotspots", arguments={"city": "london", "metric": "starts", "limit": 1, "time_filter": {}}),
        ToolDecision(kind="call_tool", tool="find_hotspots", arguments={"city": "london", "metric": "starts", "limit": 1, "time_filter": {}}),
    ]))
    result = asyncio.run(service.investigate(InvestigationRequest(question="Keep exploring")))
    assert result.status == "failed"
    assert "bounded tool-call budget" in result.answer
    assert len(mcp.calls) == 3
