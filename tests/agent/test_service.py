from __future__ import annotations

from typing import Any

import asyncio

from apps.api.app.agent.schemas import InvestigationRequest, ToolDecision
from apps.api.app.agent.places import MapsSearchResult
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


class FakeMaps:
    def __init__(self, failure: Exception | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.failure = failure

    async def search_places(self, category: str, cell: str) -> MapsSearchResult:
        self.calls.append((category, cell))
        if self.failure:
            raise self.failure
        return MapsSearchResult.model_validate({"places": [{
            "place_id": f"place-{category}", "name": "Example Cafe", "latitude": 51.5, "longitude": -0.1,
            "maps_uri": "https://maps.google.com/example", "category": category, "h3_cell": cell,
        }]})


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


def test_amenity_question_calls_city_data_before_maps_and_preserves_provenance() -> None:
    mcp = FakeMcp()
    maps = FakeMaps()
    service = InvestigationService(mcp_client=mcp, maps_client=maps, model=FakeModel([
        ToolDecision(kind="call_tool", tool="find_hotspots", arguments={"city": "london", "metric": "starts", "limit": 1, "time_filter": {}}),
        ToolDecision(kind="call_tool", tool="maps.search_places", arguments={"h3_cells": ["892a100d2d7ffff"], "categories": ["cafe"]}),
        ToolDecision(kind="answer", answer="The historical hotspot has one current Google Maps cafe result."),
    ]))

    result = asyncio.run(service.investigate(InvestigationRequest(question="Which busy areas have few cafes?")))

    assert result.status == "answered"
    assert mcp.calls[0][0] == "find_hotspots"
    assert maps.calls == [("cafe", "892a100d2d7ffff")]
    assert any(item.source == "city_data" for item in result.evidence)
    assert any(item.source == "google_maps" for item in result.evidence)
    assert result.places[0].place_id == "place-cafe"
    assert result.amenity_analysis[0]["place_count"] == 1
    assert result.trace[1].tool == "city_data.find_hotspots"
    assert result.trace[2].tool == "maps.search_places"


def test_maps_failure_returns_partial_historical_result_without_places() -> None:
    mcp = FakeMcp()
    maps = FakeMaps(RuntimeError("provider timeout"))
    service = InvestigationService(mcp_client=mcp, maps_client=maps, model=FakeModel([
        ToolDecision(kind="call_tool", tool="find_hotspots", arguments={"city": "london", "metric": "starts", "limit": 1, "time_filter": {}}),
        ToolDecision(kind="call_tool", tool="maps.search_places", arguments={"h3_cells": ["892a100d2d7ffff"], "categories": ["cafe"]}),
    ]))

    result = asyncio.run(service.investigate(InvestigationRequest(question="Which busy areas have few cafes?")))

    assert result.status == "partial"
    assert result.places == []
    assert any("unavailable" in limitation for limitation in result.limitations)


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
