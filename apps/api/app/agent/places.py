from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import httpx
from h3 import cell_to_latlng, is_valid_cell
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel, Field, field_validator

from .. import config  # noqa: F401  # Load the project environment before reading it.
from ..cities import CityId, get_city
from .schemas import AmenityCategory, PlaceResult
from .route_service import ResolvedPlace
from .errors import ProviderPayloadError, ProviderUnavailableError

MAPS_MCP_URL = "https://mapstools.googleapis.com/mcp"
DEFAULT_CANDIDATE_CELLS = 3
DEFAULT_CATEGORIES = 1
MAX_CANDIDATE_CELLS = 5
MAX_CATEGORIES = 2
MAX_SEARCH_RADIUS_M = 800
MAX_PLACES_PER_SEARCH = 10
MAX_MAPS_SEARCH_CALLS = MAX_CANDIDATE_CELLS * MAX_CATEGORIES

CATEGORY_QUERY = {
    "cafe": "cafes",
    "coffee_shop": "coffee shops",
    "bicycle_repair_shop": "bicycle repair shops",
    "restaurant": "restaurants",
    "shop": "shops",
    "public_bathroom": "public bathrooms",
    "point_of_interest": "interesting places and landmarks",
}


class AmenitySearchPlan(BaseModel):
    h3_cells: list[str] = Field(min_length=1, max_length=MAX_CANDIDATE_CELLS)
    categories: list[AmenityCategory] = Field(min_length=1, max_length=MAX_CATEGORIES)

    @field_validator("h3_cells")
    @classmethod
    def validate_cells(cls, cells: list[str]) -> list[str]:
        if any(not is_valid_cell(cell) for cell in cells):
            raise ValueError("Every amenity search cell must be a valid H3 identifier")
        return list(dict.fromkeys(cells))


def normalize_amenity_plan(question: str, plan: AmenitySearchPlan) -> AmenitySearchPlan:
    """Keep normal enrichment small; retain larger plans only when explicitly requested."""
    lowered = question.lower()
    explicit_multi_category = (
        sum(term in lowered for term in ("cafe", "cafés", "coffee shop", "coffee shops", "bike repair", "bicycle repair", "restaurant", "shop", "bathroom", "restroom", "toilet", "interesting", "landmark", "attraction")) >= 2
        or "both" in lowered
        or "and" in lowered and len(plan.categories) > 1
    )
    explicit_more_cells = any(token in lowered for token in ("top 5", "top five", "five areas", "five cells", "all five"))
    categories = plan.categories if explicit_multi_category else plan.categories[:DEFAULT_CATEGORIES]
    cells = plan.h3_cells if explicit_more_cells else plan.h3_cells[:DEFAULT_CANDIDATE_CELLS]
    return AmenitySearchPlan(h3_cells=cells, categories=categories)


class MapsSearchResult(BaseModel):
    places: list[PlaceResult] = Field(default_factory=list)
    summary: str | None = None


def deterministic_amenity_analysis(
    cells: list[str],
    categories: list[AmenityCategory],
    activity_by_cell: dict[str, float],
    results: dict[tuple[str, str], MapsSearchResult],
) -> list[dict[str, Any]]:
    """Return inspectable counts and relative ranks, not a business opportunity score."""
    rows: list[dict[str, Any]] = []
    for cell in cells:
        for category in categories:
            count = len(results.get((cell, category), MapsSearchResult()).places)
            rows.append({"h3_cell": cell, "category": category, "place_count": count, "mobility_value": activity_by_cell.get(cell, 0)})
    for category in categories:
        category_rows = [row for row in rows if row["category"] == category]
        for row in sorted(category_rows, key=lambda value: (value["place_count"], -value["mobility_value"], value["h3_cell"])):
            row["scarcity_rank"] = 1 + sum(other["place_count"] < row["place_count"] for other in category_rows)
    return sorted(rows, key=lambda row: (row["category"], -row["mobility_value"], row["place_count"], row["h3_cell"]))


def h3_centroid(cell: str) -> tuple[float, float]:
    if not is_valid_cell(cell):
        raise ValueError("Cannot derive a centroid for an invalid H3 cell")
    latitude, longitude = cell_to_latlng(cell)
    return float(latitude), float(longitude)


def google_search_arguments(category: AmenityCategory, cell: str, city: CityId = "london") -> dict[str, Any]:
    latitude, longitude = h3_centroid(cell)
    city_definition = get_city(city)
    return {
        "text_query": f"{CATEGORY_QUERY[category]} in {city_definition.maps_location}",
        "location_bias": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius_meters": MAX_SEARCH_RADIUS_M,
            }
        },
        "language_code": "en",
        "region_code": city_definition.region_code,
    }


class GoogleMapsGroundingClient:
    """MCP client restricted to Google's search_places tool."""

    def __init__(self, url: str | None = None, api_key: str | None = None, timeout_s: float = 20.0) -> None:
        self.url = url or os.getenv("CITYSCOPE_MAPS_MCP_URL", MAPS_MCP_URL)
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_GROUNDING_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
        self.timeout_s = timeout_s

    async def search_places(self, category: AmenityCategory, cell: str, city: CityId = "london") -> MapsSearchResult:
        if not self.api_key:
            raise ProviderUnavailableError("Google Maps", "API key is not configured")
        arguments = google_search_arguments(category, cell, city)
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_s) as http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=self.timeout_s)) as session:
                    tools = await session.list_tools()
                    if "search_places" not in {tool.name for tool in tools.tools}:
                        raise ProviderPayloadError("Google Maps", "search_places tool is unavailable")
                    result = await session.call_tool("search_places", arguments)
                    if result.isError:
                        raise ProviderUnavailableError("Google Maps", "search_places call failed")
                    payload = _structured_payload(result)
                    return parse_search_result(payload, category, cell, city)

    async def resolve_location(self, query: str, city: CityId = "london") -> ResolvedPlace:
        """Resolve a named endpoint through Grounding search; never accept model coordinates."""
        if not self.api_key:
            raise ProviderUnavailableError("Google Maps", "API key is not configured")
        headers = {"X-Goog-Api-Key": self.api_key, "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        city_definition = get_city(city)
        arguments = {"text_query": f"{query}, {city_definition.maps_location}", "language_code": "en", "region_code": city_definition.region_code}
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_s) as http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=self.timeout_s)) as session:
                    tools = await session.list_tools()
                    if "search_places" not in {tool.name for tool in tools.tools}:
                        raise ProviderPayloadError("Google Maps", "search_places tool is unavailable")
                    result = await session.call_tool("search_places", arguments)
                    if result.isError:
                        raise ProviderUnavailableError("Google Maps", "location resolution failed")
                    payload = _structured_payload(result)
        raw = next(iter(payload.get("places", [])), None)
        if not raw or not raw.get("location"):
            raise ProviderPayloadError("Google Maps", "named location could not be resolved")
        location = raw["location"]
        links = raw.get("googleMapsLinks") or {}
        return ResolvedPlace(name=raw.get("displayName") or raw.get("name") or query, place_id=raw.get("id"), latitude=float(location["latitude"]), longitude=float(location["longitude"]), maps_uri=links.get("placeUrl"))


def _structured_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured.get("result", structured)
    for content in getattr(result, "content", []):
        text = getattr(content, "text", None)
        if text:
            import json

            value = json.loads(text)
            if isinstance(value, dict):
                return value
    raise ProviderPayloadError("Google Maps", "structured search result was missing")


def parse_search_result(payload: dict[str, Any], category: AmenityCategory, h3_cell: str, city: CityId = "london") -> MapsSearchResult:
    south, west, north, east = get_city(city).bounds
    parsed: list[PlaceResult] = []
    for raw in payload.get("places", [])[:MAX_PLACES_PER_SEARCH]:
        location = raw.get("location") or {}
        links = raw.get("googleMapsLinks") or {}
        attribution = raw.get("attribution") or {}
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        place_id = raw.get("id")
        if not place_id or latitude is None or longitude is None:
            continue
        latitude = float(latitude)
        longitude = float(longitude)
        if not (south <= latitude <= north and west <= longitude <= east):
            continue
        attribution_title = attribution.get("title")
        fallback_name = attribution_title.removesuffix(" - Google Maps") if isinstance(attribution_title, str) and attribution_title != "Google Maps" else None
        parsed.append(PlaceResult(
            place_id=place_id,
            resource_name=raw.get("place"),
            name=raw.get("displayName") or raw.get("name") or fallback_name,
            latitude=latitude,
            longitude=longitude,
            maps_uri=links.get("placeUrl"),
            attribution_title=attribution.get("title"),
            attribution_url=attribution.get("url"),
            category=category,
            h3_cell=h3_cell,
        ))
    return MapsSearchResult(places=parsed, summary=payload.get("summary"))
