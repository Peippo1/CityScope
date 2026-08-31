from __future__ import annotations

import math
import os
import re
from typing import Any, Literal, Protocol

import httpx
from h3 import cell_to_latlng
from pydantic import BaseModel, Field
from .errors import ProviderPayloadError, ProviderUnavailableError

def h3_centroid(cell: str) -> tuple[float, float]:
    return tuple(cell_to_latlng(cell))


class RouteLocation(BaseModel):
    name: str
    place_id: str | None = None
    latitude: float
    longitude: float
    maps_uri: str | None = None
    source: Literal["google_maps"] = "google_maps"


class RouteWaypoint(BaseModel):
    h3_cell: str
    latitude: float
    longitude: float
    mobility_value: float
    score: float
    reason: str


class RouteDetails(BaseModel):
    travel_mode: Literal["bicycle"] = "bicycle"
    distance_m: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    polyline: str = Field(min_length=1)
    origin: RouteLocation
    destination: RouteLocation
    waypoints: list[RouteWaypoint] = Field(default_factory=list, max_length=2)
    source: Literal["google_routes_api"] = "google_routes_api"
    attribution_title: str | None = None
    attribution_url: str | None = None
    warning: str = "Bicycle routes are beta and may not include every suitable bicycle path; verify locally before travel."


class ResolvedPlace(BaseModel):
    name: str
    place_id: str | None = None
    latitude: float
    longitude: float
    maps_uri: str | None = None

    def as_location(self) -> RouteLocation:
        return RouteLocation.model_validate(self.model_dump())


class RouteExecutor(Protocol):
    async def compute_bicycle_route(self, origin: RouteLocation, destination: RouteLocation, waypoints: list[RouteWaypoint]) -> RouteDetails: ...


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(hav))


def select_waypoints(origin: RouteLocation, destination: RouteLocation, hotspots: list[dict[str, Any]]) -> list[RouteWaypoint]:
    """Select at most two high-activity cells near the straight-line route."""
    start, end = (origin.latitude, origin.longitude), (destination.latitude, destination.longitude)
    direct = max(_distance_m(start, end), 1.0)
    scored: list[RouteWaypoint] = []
    values = [float(item.get("value", item.get("total_activity", 0))) for item in hotspots]
    max_value = max(values or [1.0])
    for item, value in zip(hotspots, values):
        cell = item.get("h3_cell")
        if not cell:
            continue
        lat, lon = h3_centroid(cell)
        candidate = (lat, lon)
        a = _distance_m(start, candidate)
        b = _distance_m(candidate, end)
        detour = (a + b - direct) / direct
        # Equirectangular projection is sufficient for this bounded London corridor.
        x1, y1 = start[1], start[0]
        x2, y2 = end[1], end[0]
        t = max(0.0, min(1.0, ((lon - x1) * (x2 - x1) + (lat - y1) * (y2 - y1)) / max((x2 - x1) ** 2 + (y2 - y1) ** 2, 1e-12)))
        perpendicular = _distance_m(candidate, (y1 + t * (y2 - y1), x1 + t * (x2 - x1)))
        if perpendicular > 3000 or detour > 0.75:
            continue
        score = value / max_value - min(perpendicular / 3000, 1.0) * 0.5 - min(detour / 0.75, 1.0) * 0.5
        if score <= 0:
            continue
        scored.append(RouteWaypoint(h3_cell=cell, latitude=lat, longitude=lon, mobility_value=value, score=score, reason=f"Historical activity {value:g} in the May 2026 snapshot; selected as a high-activity cell near the route corridor."))
    scored.sort(key=lambda item: (-item.score, item.h3_cell))
    return scored[:2]


class GoogleRoutesService:
    def __init__(self, api_key: str | None = None, url: str | None = None, timeout_s: float = 20.0) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_ROUTES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
        self.url = url or os.getenv("CITYSCOPE_ROUTES_API_URL", "https://routes.googleapis.com/directions/v2:computeRoutes")
        self.timeout_s = timeout_s

    @staticmethod
    def _endpoint(location: RouteLocation) -> dict[str, Any]:
        if location.place_id:
            return {"placeId": location.place_id}
        return {"location": {"latLng": {"latitude": location.latitude, "longitude": location.longitude}}}

    async def compute_bicycle_route(self, origin: RouteLocation, destination: RouteLocation, waypoints: list[RouteWaypoint]) -> RouteDetails:
        if not self.api_key:
            raise ProviderUnavailableError("Google Routes", "API key is not configured")
        body = {"origin": self._endpoint(origin), "destination": self._endpoint(destination), "intermediates": [{"location": {"latLng": {"latitude": point.latitude, "longitude": point.longitude}}} for point in waypoints], "travelMode": "BICYCLE", "polylineQuality": "OVERVIEW", "polylineEncoding": "ENCODED_POLYLINE"}
        headers = {"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline,routes.legs.startLocation,routes.legs.endLocation", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(self.url, json=body, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("Google Routes", "HTTP request failed") from exc
        routes = response.json().get("routes", [])
        if not routes:
            raise ProviderPayloadError("Google Routes", "No bicycle route returned")
        route = routes[0]
        polyline = route.get("polyline", {}).get("encodedPolyline")
        duration = route.get("duration", "")
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)s", str(duration))
        if not polyline or not match or float(route.get("distanceMeters", 0)) <= 0 or float(match.group(1)) <= 0:
            raise ProviderPayloadError("Google Routes", "Google Routes API returned an invalid bicycle route")
        return RouteDetails(distance_m=int(route["distanceMeters"]), duration_seconds=float(match.group(1)), polyline=polyline, origin=origin, destination=destination, waypoints=waypoints, attribution_title="Google Routes API", attribution_url="https://developers.google.com/maps/documentation/routes")
