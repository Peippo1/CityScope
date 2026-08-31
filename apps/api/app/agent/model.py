from __future__ import annotations

import json
import os
from typing import Literal
from typing import Protocol

from pydantic import BaseModel, Field, StrictInt, field_validator

from .. import config  # noqa: F401  # Load the project environment before reading it.
from pipelines.core.analytics_contract import MetricName, TimeFilter
from services.city_data_mcp.schemas import AreaGroup, ComparisonMetric, HistoricalCityId

from .schemas import AmenityCategory, ToolDecision
from ..cities import CityId


class GeminiDecision(BaseModel):
    """Gemini-compatible schema with no arbitrary additionalProperties maps."""

    kind: Literal["call_tool", "answer", "unsupported"]
    tool: Literal["describe_dataset", "get_area_metrics", "find_hotspots", "compare_areas", "compare_cities", "maps.search_places", "route.intent"] | None = None
    city: CityId | None = None
    cities: list[HistoricalCityId] | None = None
    comparison_metric: ComparisonMetric | None = None
    metric: MetricName | None = None
    limit: int | None = None
    time_filter: TimeFilter | None = None
    h3_cells: list[str] | None = None
    metrics: list[MetricName] | None = None
    area_groups: list[AreaGroup] | None = None
    categories: list[AmenityCategory] | None = None
    origin: str | None = None
    destination: str | None = None
    return_to_origin: bool | None = None
    requested_stops: list[AmenityCategory] | None = None
    preferences: list[str] | None = None
    template_id: str | None = None
    travel_mode: Literal["bicycle", "walking"] | None = None
    answer: str | None = None
    follow_up_suggestions: list[str] = Field(default_factory=list, max_length=3)


class JourneyCharacterScore(BaseModel):
    """Bounded, non-authoritative qualitative scoring returned by Gemma."""

    scenic: StrictInt
    green: StrictInt
    lively: StrictInt
    cultural: StrictInt
    relaxed: StrictInt
    coffee: StrictInt
    rationale: str = Field(min_length=1, max_length=500)

    @field_validator("scenic", "green", "lively", "cultural", "relaxed", "coffee")
    @classmethod
    def score_must_be_bounded(cls, value: int) -> int:
        if isinstance(value, bool) or not 0 <= value <= 10:
            raise ValueError("journey character scores must be integers from 0 to 10")
        return value


class InvestigationModel(Protocol):
    async def decide(self, question: str, context: str, tool_results: list[dict]) -> ToolDecision:
        ...


class GeminiInvestigationModel:
    """Small structured-output adapter; tool execution remains owned by the agent."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("CITYSCOPE_GEMINI_MODEL", "gemini-3.5-flash")

    async def decide(self, question: str, context: str, tool_results: list[dict]) -> ToolDecision:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("The google-genai package is required for Gemini investigations") from exc

        client = genai.Client(api_key=self.api_key)
        prompt = f"""You are the CityScope investigation planner for a selected city.
Use City Data MCP for historical mobility evidence and Google Maps Grounding Lite only for bounded current place context.
Never invent current or live facts. Supported questions include historical dataset description, H3 activity hotspots,
metrics for supplied H3 cells, comparisons between supplied H3 groups, and amenity-enriched questions about cafes,
coffee shops, bicycle repair shops, restaurants, shops, or public bathrooms around trusted candidate H3 cells.
Reject questions about weather, traffic, demographics, revenue, forecasts, unnamed areas, or cities that do not match the selected request city. Historical cities are London, New York City, Chicago, and Washington, DC; each has a small city-specific curated route library. Paris and the other route-enabled cities support cycling and running route planning through curated route hints and Google Routes, but they do not support historical-demand claims.
For route.intent, return origin and destination as the user's named places. For a loop set return_to_origin=true. Set travel_mode to walking for running routes (Google Routes walking geometry is used as a safe running approximation), otherwise bicycle. Extract only requested_stops from cafe, restaurant, public_bathroom, shop, bicycle_repair_shop, point_of_interest, and preferences from scenic, quiet, park, coffee, lunch, interesting. You may provide a short template_id only when the user clearly names a known route idea; otherwise the application matches curated route templates for the selected city deterministically. Do not call or construct a Routes API request; routing is a private backend execution step.
Return JSON matching the requested schema. Call at most one tool per decision.
Tools: describe_dataset(city); find_hotspots(city, metric, time_filter, limit);
get_area_metrics(city, h3_cells, metrics, time_filter); compare_areas(city, area_groups, metrics, time_filter);
compare_cities(cities, comparison_metric). Cross-city comparison accepts two to four historical cities and only these normalized metrics:
trips_per_active_station_day, median_trip_duration_minutes, peak_hour_share, weekend_share, hotspot_concentration. Never rank raw totals.
For amenity enrichment, use maps.search_places only after City Data has supplied candidate H3 cells.
Its internal planning arguments are {{"h3_cells": [...], "categories": ["cafe"|"coffee_shop"|"bicycle_repair_shop"|"restaurant"|"shop"|"public_bathroom"|"point_of_interest"]}}.
The application derives all coordinates and sends the exact Google search_places schema. Never provide coordinates or Place IDs.
Use 3 H3 cells and 1 amenity category by default. Use up to 5 cells or 2 categories only when the user explicitly asks for that broader comparison. Historical wording must identify the mobility snapshot; place wording must identify current Google Maps context.

Question: {question}
Context: {context}
Previous tool results: {json.dumps(tool_results, default=str)}
"""
        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": GeminiDecision.model_json_schema()},
        )
        decision = GeminiDecision.model_validate_json(response.text)
        arguments = {
            key: value
            for key, value in {
                "city": decision.city,
                "cities": decision.cities,
                "metric": decision.comparison_metric or decision.metric,
                "limit": decision.limit,
                "time_filter": decision.time_filter.model_dump(mode="json") if decision.time_filter else None,
                "h3_cells": decision.h3_cells,
                "metrics": decision.metrics,
                "area_groups": [group.model_dump(mode="json") for group in decision.area_groups] if decision.area_groups else None,
                "categories": decision.categories,
                "origin": decision.origin,
                "destination": decision.destination,
                "return_to_origin": decision.return_to_origin,
                "requested_stops": decision.requested_stops,
                "preferences": decision.preferences,
                "template_id": decision.template_id,
                "travel_mode": decision.travel_mode,
            }.items()
            if value is not None
        }
        return ToolDecision(kind=decision.kind, tool=decision.tool, arguments=arguments, answer=decision.answer, follow_up_suggestions=decision.follow_up_suggestions)


class GemmaJourneyCharacterScorer:
    """Optional one-call Gemma scorer with local validation and no raw payload retention."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("CITYSCOPE_GEMMA_MODEL", "gemma-4-26b-a4b-it")

    async def score(self, question: str, evidence_summary: str) -> JourneyCharacterScore:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("The google-genai package is required for Gemma scoring") from exc
        client = genai.Client(api_key=self.api_key)
        prompt = (
            "Score the requested journey character using only the supplied historical evidence. "
            "Return JSON with integer fields scenic, green, lively, cultural, relaxed, coffee (0-10) "
            "and a short rationale. Do not invent facts.\n"
            f"Question: {question}\nEvidence: {evidence_summary}"
        )
        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return JourneyCharacterScore.model_validate_json(text)
