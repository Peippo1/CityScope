from __future__ import annotations

from typing import Any

import asyncio
import time

from apps.api.app.agent.schemas import InvestigationRequest, ToolDecision
from apps.api.app.agent.places import MapsSearchResult
from apps.api.app.agent.model import GeminiInvestigationModel
from apps.api.app.agent.route_service import ResolvedPlace, RouteDetails
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


def test_gemini_defaults_to_hackathon_compatible_stable_model(monkeypatch) -> None:
    monkeypatch.delenv("CITYSCOPE_GEMINI_MODEL", raising=False)

    assert GeminiInvestigationModel(api_key="test").model_name == "gemini-3.5-flash"


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

    async def resolve_location(self, query: str) -> ResolvedPlace:
        raise NotImplementedError


class RouteMaps(FakeMaps):
    def __init__(self) -> None:
        super().__init__()
        self.resolution_calls: list[str] = []

    async def resolve_location(self, query: str) -> ResolvedPlace:
        self.resolution_calls.append(query)
        if query == "King's Cross":
            return ResolvedPlace(name=query, place_id="place-origin", latitude=51.5308, longitude=-0.1238, maps_uri="https://maps.google.com/origin")
        return ResolvedPlace(name=query, place_id="place-destination", latitude=51.5033, longitude=-0.1195, maps_uri="https://maps.google.com/destination")


class FakeRouteService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    async def compute_bicycle_route(self, origin, destination, waypoints):
        self.calls.append((origin.place_id or "", destination.place_id or "", len(waypoints)))
        return RouteDetails(distance_m=2400, duration_seconds=900, polyline="encoded-route", origin=origin, destination=destination, waypoints=waypoints)


class ConcurrentMaps(FakeMaps):
    def __init__(self) -> None:
        super().__init__()
        self.active = 0
        self.max_active = 0

    async def search_places(self, category: str, cell: str) -> MapsSearchResult:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return await super().search_places(category, cell)


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


def test_weather_policy_rejects_before_model_or_maps_execution() -> None:
    mcp = FakeMcp()
    maps = FakeMaps()
    service = InvestigationService(mcp_client=mcp, maps_client=maps, model=FakeModel([]))

    result = asyncio.run(service.investigate(InvestigationRequest(question="What's the weather in the busiest cycling area?")))

    assert result.status == "unsupported"
    assert not mcp.calls
    assert not maps.calls


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


def test_amenity_enrichment_uses_three_by_one_default_and_parallel_calls() -> None:
    mcp = FakeMcp()
    maps = ConcurrentMaps()
    cells = ["89194ad3353ffff", "89194ad3203ffff", "89194ad32cbffff", "89194ad330fffff"]
    service = InvestigationService(mcp_client=mcp, maps_client=maps, model=FakeModel([
        ToolDecision(kind="call_tool", tool="find_hotspots", arguments={"city": "london", "metric": "starts", "limit": 1, "time_filter": {}}),
        ToolDecision(kind="call_tool", tool="maps.search_places", arguments={"h3_cells": cells, "categories": ["cafe", "coffee_shop"]}),
        ToolDecision(kind="answer", answer="The comparison is complete."),
    ]))
    request = InvestigationRequest(question="Which busy areas have few cafes nearby?", context={"selected_h3_cells": cells})

    started = time.perf_counter()
    result = asyncio.run(service.investigate(request))
    elapsed = time.perf_counter() - started

    assert result.status == "answered"
    assert len(maps.calls) == 3
    assert maps.max_active >= 2
    assert elapsed < 0.12


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


def test_route_intent_executes_city_data_then_private_route_adapter_without_routes_tool() -> None:
    mcp = FakeMcp()
    maps = RouteMaps()
    route_service = FakeRouteService()
    service = InvestigationService(mcp_client=mcp, maps_client=maps, route_service=route_service, model=FakeModel([
        ToolDecision(kind="call_tool", tool="route.intent", arguments={"origin": "King's Cross", "destination": "Borough"}),
    ]))

    result = asyncio.run(service.investigate(InvestigationRequest(question="How can I cycle from King's Cross to Borough?")))

    assert result.status == "answered"
    assert maps.resolution_calls == ["King's Cross", "Borough"]
    assert mcp.calls == [("find_hotspots", {"city": "london", "metric": "total_activity", "limit": 10, "time_filter": {}})]
    assert route_service.calls == [("place-origin", "place-destination", 0)]
    assert result.route is not None and result.route.polyline == "encoded-route"
    assert all("secret" not in event.label for event in result.trace)
    assert "compute_routes" not in {event.tool for event in result.trace}


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
