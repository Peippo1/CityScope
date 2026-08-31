from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pipelines.core.analytics_contract import MetricName, TimeFilter
from ..cities import CityId
from services.city_data_mcp.schemas import DatasetMetadata, Evidence, MapLayer

AmenityCategory = Literal["cafe", "coffee_shop", "bicycle_repair_shop", "restaurant", "shop", "public_bathroom", "point_of_interest"]
JourneyStopCategory = Literal["cafe", "restaurant", "public_bathroom", "shop", "bicycle_repair_shop", "point_of_interest"]


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class InvestigationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_h3_cells: list[str] = Field(default_factory=list, max_length=50)
    previous_turns: list[ConversationTurn] = Field(default_factory=list, max_length=6)
    evidence_summary: str | None = Field(default=None, max_length=2000)


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: CityId = "london"
    question: str = Field(min_length=1, max_length=500)
    context: InvestigationContext = Field(default_factory=InvestigationContext)


class TraceEvent(BaseModel):
    kind: Literal["planning", "tool_call", "synthesis"]
    label: str
    status: Literal["completed", "rejected", "failed"]
    tool: str | None = None
    provider: str | None = None
    result_count: int | None = None
    latency_ms: int | None = None
    policy_code: str | None = None
    call_number: int | None = Field(default=None, ge=1)
    budget_limit: int | None = Field(default=None, ge=1)


class InvestigationResult(BaseModel):
    investigation_id: str
    status: Literal["answered", "partial", "unsupported", "failed"]
    answer: str
    dataset: DatasetMetadata | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    places: list["PlaceResult"] = Field(default_factory=list)
    amenity_analysis: list[dict[str, Any]] = Field(default_factory=list)
    route: "RouteDetails | None" = None
    journey_plan: "JourneyPlan | None" = None
    city_insights: list[dict[str, Any]] = Field(default_factory=list)
    map_layers: list[MapLayer] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list, max_length=3)
    journey_character_score: dict[str, Any] | None = None


class ToolDecision(BaseModel):
    kind: Literal["call_tool", "answer", "unsupported"]
    tool: Literal["describe_dataset", "get_area_metrics", "find_hotspots", "compare_areas", "compare_cities", "maps.search_places", "route.intent"] | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    answer: str | None = Field(default=None, max_length=1200)
    follow_up_suggestions: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("arguments")
    @classmethod
    def bound_arguments(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 12:
            raise ValueError("Tool arguments are too large")
        return value


class ToolCallSpec(BaseModel):
    tool: str
    arguments: dict[str, Any]


def default_time_filter() -> TimeFilter:
    return TimeFilter()


class PlaceResult(BaseModel):
    place_id: str
    resource_name: str | None = None
    name: str | None = None
    latitude: float
    longitude: float
    maps_uri: str | None = None
    attribution_title: str | None = None
    attribution_url: str | None = None
    category: AmenityCategory
    h3_cell: str


class JourneySegment(BaseModel):
    label: str
    route: "RouteDetails"
    purpose: str | None = None


class JourneyPlan(BaseModel):
    summary: str
    segments: list[JourneySegment] = Field(default_factory=list, max_length=2)
    selected_stops: list[PlaceResult] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=10)
    provenance: list[str] = Field(default_factory=list, max_length=10)
    template_id: str | None = None
    template_name: str | None = None
    template_description: str | None = None
    template_tags: list[str] = Field(default_factory=list, max_length=6)
    template_source_url: str | None = None
    template_notice: str | None = None
    template_waypoint_hints: list[str] = Field(default_factory=list, max_length=4)


from .route_service import RouteDetails  # noqa: E402  # Imported after schemas to avoid model import cycles.
