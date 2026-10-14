from __future__ import annotations

import os
import json
import math
import re
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx
from h3 import cell_to_latlng, is_valid_cell
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel, Field, field_validator

from .. import config  # noqa: F401  # Load the project environment before reading it.
from ..cities import CityId, get_city
from .schemas import AmenityCategory, PlaceResult
from .route_service import ResolvedPlace
from .errors import ProviderOperationError, ProviderPayloadError, ProviderUnavailableError

MAPS_MCP_URL = "https://mapstools.googleapis.com/mcp"
MAPS_RESOLUTION_URL = "https://mapstools.googleapis.com/v1:resolveNames"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places"
DEFAULT_CANDIDATE_CELLS = 3
DEFAULT_CATEGORIES = 1
MAX_CANDIDATE_CELLS = 5
MAX_CATEGORIES = 2
MAX_SEARCH_RADIUS_M = 800
MAX_PLACES_PER_SEARCH = 10
MAX_MAPS_SEARCH_CALLS = MAX_CANDIDATE_CELLS * MAX_CATEGORIES
GENERIC_LOCATION_TOKENS = {"city", "centre", "center", "district", "road", "street", "st", "station", "uk", "usa"}

CATEGORY_QUERY = {
    "cafe": "cafes",
    "coffee_shop": "coffee shops",
    "bicycle_repair_shop": "bicycle repair shops",
    "restaurant": "restaurants",
    "shop": "shops",
    "public_bathroom": "public bathrooms",
    "point_of_interest": "interesting places and landmarks",
}

LOCALE_LANGUAGE = {"en-GB": "en", "fr-FR": "fr", "es-ES": "es", "it-IT": "it"}
CITY_LANGUAGE = {"FR": "fr", "ES": "es", "IT": "it"}


def _safe_google_url(value: Any) -> str | None:
    """Keep provider-supplied links navigable without trusting arbitrary URLs."""
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not hostname.endswith(".google.com") and hostname not in {"google.com"}:
        return None
    return value


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


def google_search_arguments(category: AmenityCategory, cell: str, city: CityId = "london", locale: str | None = None) -> dict[str, Any]:
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
        "language_code": LOCALE_LANGUAGE.get(locale or "", CITY_LANGUAGE.get(city_definition.region_code, "en")),
        "region_code": city_definition.region_code,
    }


class GoogleMapsGroundingClient:
    """Use Grounding for discovery and deterministic APIs for named endpoints."""

    def __init__(self, url: str | None = None, api_key: str | None = None, timeout_s: float = 20.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.url = url or os.getenv("CITYSCOPE_MAPS_MCP_URL", MAPS_MCP_URL)
        self.resolution_url = os.getenv("CITYSCOPE_MAPS_RESOLUTION_URL", MAPS_RESOLUTION_URL)
        self.place_details_url = os.getenv("CITYSCOPE_PLACES_API_URL", PLACES_DETAILS_URL).rstrip("/")
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_GROUNDING_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
        self.timeout_s = timeout_s
        self.transport = transport

    async def search_places(self, category: AmenityCategory, cell: str, city: CityId = "london", locale: str | None = None) -> MapsSearchResult:
        if not self.api_key:
            raise ProviderUnavailableError("Google Maps", "API key is not configured")
        arguments = google_search_arguments(category, cell, city, locale)
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_s, transport=self.transport) as http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=self.timeout_s)) as session:
                    tools = await session.list_tools()
                    if "search_places" not in {tool.name for tool in tools.tools}:
                        raise ProviderPayloadError("Google Maps", "search_places tool is unavailable", reason_code="tool_unavailable")
                    result = await session.call_tool("search_places", arguments)
                    if result.isError:
                        raise ProviderOperationError("Google Maps", "search_places call failed")
                    payload = _structured_payload(result)
                    return parse_search_result(payload, category, cell, city)

    async def resolve_location(self, query: str, city: CityId = "london", locale: str | None = None) -> ResolvedPlace:
        """Resolve one named endpoint through Resolution API plus Place Details."""
        return (await self.resolve_locations([query], city, locale))[0]

    async def resolve_locations(self, queries: list[str], city: CityId = "london", locale: str | None = None) -> list[ResolvedPlace]:
        """Resolve bounded named endpoints without relying on discovery summaries."""
        if not self.api_key:
            raise ProviderUnavailableError("Google Maps", "API key is not configured")
        if not 1 <= len(queries) <= 2 or any(not isinstance(query, str) or not query.strip() for query in queries):
            raise ProviderPayloadError("Google Maps", "named endpoint resolution request was invalid", reason_code="resolution_response_invalid")
        city_definition = get_city(city)
        headers = {"X-Goog-Api-Key": self.api_key, "Content-Type": "application/json"}
        arguments = {
            "queries": [{"text": f"{query.strip()}, {city_definition.maps_location}"} for query in queries],
            "locationBias": {"viewport": {"low": {"latitude": city_definition.bounds[0], "longitude": city_definition.bounds[1]}, "high": {"latitude": city_definition.bounds[2], "longitude": city_definition.bounds[3]}}},
            "regionCode": city_definition.region_code,
        }
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_s, transport=self.transport) as http_client:
            resolution = await _json_request(http_client, "POST", self.resolution_url, arguments, "Google Maps")
            results = resolution.get("results")
            if not isinstance(results, list) or len(results) != len(queries):
                raise ProviderPayloadError("Google Maps", reason_code="resolution_response_invalid")
            resolved_ids: list[str] = []
            for index, result in enumerate(results):
                if not isinstance(result, dict) or not result:
                    raise ProviderPayloadError("Google Maps", "named location was not found", reason_code="resolution_no_match")
                if result.get("confidence") != "HIGH":
                    raise ProviderPayloadError("Google Maps", "named location was ambiguous", reason_code="resolution_low_confidence")
                entity = result.get("entity")
                resource = entity.get("place") if isinstance(entity, dict) else None
                if not isinstance(resource, str) or not re.fullmatch(r"places/[A-Za-z0-9_-]+", resource):
                    raise ProviderPayloadError("Google Maps", reason_code="resolution_missing_place_id")
                resolved_ids.append(resource)
            details: list[ResolvedPlace] = []
            for query, resource in zip(queries, resolved_ids, strict=True):
                details.append(await self._place_details(http_client, resource, query, city))
        return details

    async def resolve_place_id(self, place_id: str, city: CityId = "london", name: str = "Selected location") -> ResolvedPlace:
        """Server-validate a public Place ID before it can be used for routing."""
        resource = place_id if place_id.startswith("places/") else f"places/{place_id}"
        if not re.fullmatch(r"places/[A-Za-z0-9_-]+", resource):
            raise ProviderPayloadError("Google Places", reason_code="resolution_missing_place_id")
        if not self.api_key:
            raise ProviderUnavailableError("Google Places", "API key is not configured")
        headers = {"X-Goog-Api-Key": self.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout_s, transport=self.transport) as http_client:
            return await self._place_details(http_client, resource, name, city)

    async def _place_details(self, client: httpx.AsyncClient, resource: str, name: str, city: CityId) -> ResolvedPlace:
        payload = await _json_request(client, "GET", f"{self.place_details_url}/{resource.removeprefix('places/')}", None, "Google Places")
        location = payload.get("location") if isinstance(payload, dict) else None
        latitude = location.get("latitude") if isinstance(location, dict) else None
        longitude = location.get("longitude") if isinstance(location, dict) else None
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise ProviderPayloadError("Google Places", reason_code="details_missing_location")
        if not math.isfinite(latitude) or not math.isfinite(longitude) or not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            raise ProviderPayloadError("Google Places", reason_code="details_invalid_geometry")
        south, west, north, east = get_city(city).bounds
        if not (south <= latitude <= north and west <= longitude <= east):
            raise ProviderPayloadError("Google Places", "selected location is outside the selected city", reason_code="candidate_outside_city")
        return ResolvedPlace(name=name.strip() or "Selected location", place_id=resource.removeprefix("places/"), latitude=float(latitude), longitude=float(longitude))

    @staticmethod
    def resolve_selected_location(
        *,
        name: str,
        place_id: str | None,
        latitude: float | None,
        longitude: float | None,
    ) -> ResolvedPlace:
        """Use a user-selected location without sending precise coordinates to an LLM or persisting them."""
        if place_id and (latitude is not None or longitude is not None):
            raise ProviderPayloadError("Google Maps", "provide either a Place ID or coordinates for a selected location, not both")
        if (latitude is None) != (longitude is None):
            raise ProviderPayloadError("Google Maps", "selected coordinates must include both latitude and longitude")
        if not place_id and latitude is None:
            raise ProviderPayloadError("Google Maps", "a selected location requires a Place ID or coordinate pair")
        return ResolvedPlace(name=name.strip() or "Selected location", place_id=place_id, latitude=latitude, longitude=longitude)


def _structured_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        if not isinstance(structured, dict):
            raise ProviderPayloadError("Google Maps", reason_code="structured_wrapper_invalid")
        if "result" in structured:
            structured = structured["result"]
            if not isinstance(structured, dict):
                raise ProviderPayloadError("Google Maps", reason_code="structured_wrapper_invalid")
        return structured
    saw_text = False
    for content in getattr(result, "content", []):
        text = getattr(content, "text", None)
        if text:
            saw_text = True
            try:
                value = json.loads(text)
            except (TypeError, ValueError) as exc:
                raise ProviderPayloadError("Google Maps", reason_code="json_content_invalid") from exc
            if isinstance(value, dict):
                return value
            raise ProviderPayloadError("Google Maps", reason_code="json_content_invalid")
    reason_code = "json_content_invalid" if saw_text else "structured_content_missing"
    raise ProviderPayloadError("Google Maps", "structured search result was missing", reason_code=reason_code)


async def _json_request(client: httpx.AsyncClient, method: str, url: str, body: dict[str, Any] | None, provider: str) -> dict[str, Any]:
    response = await client.request(method, url, json=body, headers={"X-Goog-FieldMask": "location"} if method == "GET" else None)
    response.raise_for_status()
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise ProviderPayloadError(provider, reason_code="resolution_response_invalid") from exc
    if not isinstance(payload, dict):
        raise ProviderPayloadError(provider, reason_code="resolution_response_invalid")
    return payload


def resolve_place_from_payload(payload: dict[str, Any], query: str, city: CityId) -> ResolvedPlace:
    """Select the first verified in-city candidate, skipping incomplete results."""
    if "places" not in payload:
        raise ProviderPayloadError("Google Maps", reason_code="places_collection_missing")
    places = payload["places"]
    if not isinstance(places, list):
        raise ProviderPayloadError("Google Maps", reason_code="places_collection_invalid")
    if not places:
        raise ProviderPayloadError("Google Maps", "named location was not found", reason_code="places_empty")

    south, west, north, east = get_city(city).bounds
    saw_outside_city = False
    saw_invalid_geometry = False
    saw_incomplete_or_unrelated = False
    city_tokens = {token for token in re.findall(r"[\w]+", get_city(city).name.casefold()) if len(token) > 1}
    query_tokens = {
        token for token in re.findall(r"[\w]+", query.casefold())
        if len(token) > 1 and token not in city_tokens and token not in GENERIC_LOCATION_TOKENS
    }
    for raw in places[:MAX_PLACES_PER_SEARCH]:
        if not isinstance(raw, dict):
            saw_incomplete_or_unrelated = True
            continue
        location = raw.get("location")
        place_id = raw.get("id")
        if not isinstance(location, dict) or not isinstance(place_id, str) or not place_id.strip():
            saw_incomplete_or_unrelated = True
            continue
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)) or not math.isfinite(latitude) or not math.isfinite(longitude) or not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            saw_invalid_geometry = True
            continue
        if not (south <= latitude <= north and west <= longitude <= east):
            saw_outside_city = True
            continue
        candidate_name = raw.get("displayName") or raw.get("name")
        candidate_tokens = {token for token in re.findall(r"[\w]+", candidate_name.casefold()) if len(token) > 1} if isinstance(candidate_name, str) else set()
        if not query_tokens or not query_tokens.intersection(candidate_tokens):
            saw_incomplete_or_unrelated = True
            continue
        links = raw.get("googleMapsLinks") or {}
        return ResolvedPlace(name=raw.get("displayName") or raw.get("name") or query, place_id=place_id, latitude=float(latitude), longitude=float(longitude), maps_uri=_safe_google_url(links.get("placeUrl")))
    if saw_outside_city and not saw_invalid_geometry and not saw_incomplete_or_unrelated:
        reason_code = "candidate_outside_city"
    elif saw_invalid_geometry:
        reason_code = "invalid_candidate_geometry"
    elif saw_incomplete_or_unrelated:
        reason_code = "candidate_not_relevant"
    else:
        reason_code = "no_usable_candidate"
    raise ProviderPayloadError("Google Maps", "named location could not be resolved", reason_code=reason_code)


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
            maps_uri=_safe_google_url(links.get("placeUrl")),
            attribution_title=attribution.get("title"),
            attribution_url=_safe_google_url(attribution.get("url")),
            category=category,
            h3_cell=h3_cell,
        ))
    return MapsSearchResult(places=parsed, summary=payload.get("summary"))
