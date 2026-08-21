from __future__ import annotations

import json
import time
import uuid
from typing import Any

from services.city_data_mcp.schemas import DatasetMetadata, ToolEnvelope

from .mcp_client import CityDataMcpClient
from .model import GeminiInvestigationModel, InvestigationModel
from .places import MAX_MAPS_SEARCH_CALLS, AmenitySearchPlan, GoogleMapsGroundingClient, deterministic_amenity_analysis
from .schemas import InvestigationRequest, InvestigationResult, TraceEvent, ToolDecision

MAX_TOOL_ROUNDS = 3
ALLOWED_TOOLS = {"describe_dataset", "get_area_metrics", "find_hotspots", "compare_areas", "maps.search_places"}


class InvestigationService:
    def __init__(self, mcp_client: CityDataMcpClient | Any | None = None, maps_client: GoogleMapsGroundingClient | Any | None = None, model: InvestigationModel | None = None) -> None:
        self.mcp_client = mcp_client or CityDataMcpClient()
        self.maps_client = maps_client or GoogleMapsGroundingClient()
        self.model = model or GeminiInvestigationModel()

    async def investigate(self, request: InvestigationRequest) -> InvestigationResult:
        investigation_id = str(uuid.uuid4())
        trace = [TraceEvent(kind="planning", label="Classify question and select a City Data MCP tool", status="completed")]
        context = request.context.model_dump_json()
        tool_results: list[dict] = []
        envelope: ToolEnvelope | None = None
        final_decision: ToolDecision | None = None
        places = []
        external_evidence = []
        map_results: dict[tuple[str, str], Any] = {}
        map_plan: AmenitySearchPlan | None = None
        amenity_analysis: list[dict] = []

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                decision = await self.model.decide(request.question, context, tool_results)
            except Exception as exc:
                trace.append(TraceEvent(kind="planning", label="Model decision failed", status="failed"))
                return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The investigation could not be planned.", limitations=[str(exc)], trace=trace)
            final_decision = decision
            if decision.kind == "unsupported":
                return InvestigationResult(investigation_id=investigation_id, status="unsupported", answer=decision.answer or "I can answer historical London mobility questions about the available dataset, hotspots, H3 metrics, and area comparisons.", limitations=["This question is outside the supported CityScope V1 investigation scope."], trace=trace, follow_up_suggestions=decision.follow_up_suggestions)
            if decision.kind == "answer":
                break
            if decision.tool not in ALLOWED_TOOLS:
                trace.append(TraceEvent(kind="tool_call", label="Rejected unsupported tool", status="rejected", tool=decision.tool))
                return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The investigation requested an unsupported data operation.", limitations=["Only the four City Data MCP tools are available in V1."], trace=trace)
            if decision.tool == "maps.search_places":
                if envelope is None and not request.context.selected_h3_cells:
                    trace.append(TraceEvent(kind="tool_call", label="Rejected Maps search before candidate narrowing", status="rejected", tool="maps.search_places"))
                    return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The place search was rejected because no trusted candidate H3 cells were available.", limitations=["City Data MCP must narrow an amenity-enriched search before Maps enrichment."], trace=trace)
                try:
                    map_plan = AmenitySearchPlan.model_validate(decision.arguments)
                    trusted_cells = set(request.context.selected_h3_cells)
                    if envelope:
                        trusted_cells.update(layer.h3_cell for layer in envelope.map_layers)
                    if not set(map_plan.h3_cells).issubset(trusted_cells):
                        raise ValueError("Maps search cells must come from City Data results or selected H3 cells")
                    if len(map_plan.h3_cells) * len(map_plan.categories) > MAX_MAPS_SEARCH_CALLS:
                        raise ValueError("Maps search exceeded the bounded call limit")
                except Exception as exc:
                    trace.append(TraceEvent(kind="tool_call", label="Rejected invalid Maps enrichment plan", status="rejected", tool="maps.search_places"))
                    return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The place search plan was invalid.", limitations=[str(exc)], trace=trace)
                for cell in map_plan.h3_cells:
                    for category in map_plan.categories:
                        started = time.perf_counter()
                        try:
                            result = await self.maps_client.search_places(category, cell)
                        except Exception as exc:
                            trace.append(TraceEvent(kind="tool_call", label="Google Maps place enrichment unavailable", status="failed", tool="maps.search_places", latency_ms=round((time.perf_counter() - started) * 1000)))
                            historical_evidence = envelope.evidence if envelope else []
                            return InvestigationResult(investigation_id=investigation_id, status="partial", answer="The historical CityScope analysis is available, but current Google Maps place enrichment could not be completed.", dataset=envelope.dataset if envelope else None, evidence=historical_evidence, map_layers=envelope.map_layers if envelope else [], places=places, limitations=["Google Maps Grounding Lite was unavailable for this request.", str(exc)], trace=trace)
                        map_results[(cell, category)] = result
                        places.extend(result.places)
                        external_evidence.append({"source": "google_maps", "metric": "place_count", "value": len(result.places), "unit": "places", "source_aggregate": "maps.search_places", "filters_applied": {"category": category}, "h3_cells": [cell], "category": category, "search_radius_m": 800})
                        trace.append(TraceEvent(kind="tool_call", label="Called Google Maps Grounding MCP: search_places", status="completed", tool="maps.search_places", result_count=len(result.places), latency_ms=round((time.perf_counter() - started) * 1000)))
                activity_by_cell = {layer.h3_cell: float(layer.value) for layer in (envelope.map_layers if envelope else [])}
                amenity_analysis = deterministic_amenity_analysis(map_plan.h3_cells, map_plan.categories, activity_by_cell, map_results)
                tool_results.append({"source": "google_maps", "places": [place.model_dump(mode="json") for place in places], "amenity_analysis": amenity_analysis})
                context = json.dumps({"request": request.context.model_dump(mode="json"), "available_evidence": tool_results}, default=str)
                continue
            try:
                envelope_data = await self.mcp_client.call(decision.tool, decision.arguments)
                if decision.tool == "describe_dataset":
                    dataset = DatasetMetadata.model_validate(envelope_data)
                    envelope = ToolEnvelope(dataset=dataset, results=[], evidence=[], map_layers=[], limitations=dataset.limitations)
                else:
                    envelope = ToolEnvelope.model_validate(envelope_data)
                tool_results.append({"source": "city_data", **envelope.model_dump(mode="json")})
                trace.append(TraceEvent(kind="tool_call", label=f"Called City Data MCP: {decision.tool}", status="completed", tool=f"city_data.{decision.tool}", result_count=len(envelope.results)))
            except Exception as exc:
                trace.append(TraceEvent(kind="tool_call", label=f"City Data MCP call failed: {decision.tool}", status="failed", tool=decision.tool))
                return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The City Data MCP service could not answer this investigation.", limitations=[str(exc)], trace=trace)
            context = json.dumps({"request": request.context.model_dump(mode="json"), "available_evidence": tool_results}, default=str)

        if envelope is None and not places:
            return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The investigation did not produce a grounded result.", limitations=["A City Data or Google Maps result is required before synthesis."], trace=trace)
        if final_decision is None or final_decision.kind != "answer":
            return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The investigation exceeded its bounded tool-call budget.", limitations=[f"Maximum tool-call rounds: {MAX_TOOL_ROUNDS}"], trace=trace)
        trace.append(TraceEvent(kind="synthesis", label="Synthesize an evidence-grounded answer", status="completed"))
        from services.city_data_mcp.schemas import Evidence

        maps_evidence = [Evidence.model_validate(item) for item in external_evidence]
        limitations = list(dict.fromkeys((envelope.limitations if envelope else []) + (["Google Maps place counts are current search context, not an exhaustive census."] if external_evidence else [])))
        return InvestigationResult(investigation_id=investigation_id, status="answered", answer=final_decision.answer or "No answer was returned.", dataset=envelope.dataset if envelope else None, evidence=(envelope.evidence if envelope else []) + maps_evidence, places=places, amenity_analysis=amenity_analysis, map_layers=envelope.map_layers if envelope else [], limitations=limitations, trace=trace, follow_up_suggestions=final_decision.follow_up_suggestions)
