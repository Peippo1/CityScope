from __future__ import annotations

import math
import os
import re
from typing import Any, Literal, Protocol

import httpx
from h3 import cell_to_latlng
from pydantic import BaseModel, Field
from .errors import ProviderPayloadError, ProviderUnavailableError

ROUTE_CORRIDOR_METERS = 3000.0
MAX_AUTOMATIC_WAYPOINT_DETOUR = 0.75
MIN_RUNNING_FACILITY_CORRIDOR_METERS = 250.0
MIN_CYCLING_FACILITY_CORRIDOR_METERS = 500.0
FACILITY_CORRIDOR_ROUTE_RATIO = 0.05
MAX_ENCODED_POLYLINE_CHARS = 500_000
_GENERIC_WAYPOINT_QUERY = re.compile(
    r"^(?:a|an|any|some)\s+(?:.+\s+)?(?:cafe|caf[eé]|coffee shop|restaurant|toilet|bathroom)"
    r"(?:\s+(?:nearby|halfway|along the way|on the route))?$|"
    r"\b(?:nearby|halfway|along the way|on the route)\b",
    re.IGNORECASE,
)

def h3_centroid(cell: str) -> tuple[float, float]:
    return tuple(cell_to_latlng(cell))


class RouteLocation(BaseModel):
    name: str
    place_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
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
    travel_mode: Literal["bicycle", "walking"] = "bicycle"
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
    latitude: float | None = None
    longitude: float | None = None
    maps_uri: str | None = None

    def as_location(self) -> RouteLocation:
        return RouteLocation.model_validate(self.model_dump())


class RouteExecutor(Protocol):
    async def compute_bicycle_route(self, origin: RouteLocation, destination: RouteLocation, waypoints: list[RouteWaypoint]) -> RouteDetails: ...
    async def compute_walking_route(self, origin: RouteLocation, destination: RouteLocation, waypoints: list[RouteWaypoint]) -> RouteDetails: ...


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat = lat2 - lat1
    dlon = math.radians(_longitude_delta(a[1], b[1]))
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(hav))


def _longitude_delta(start: float, end: float) -> float:
    """Return the shortest signed longitude delta in degrees."""
    return (end - start + 180.0) % 360.0 - 180.0


def _normalize_longitude(longitude: float) -> float:
    return (longitude + 180.0) % 360.0 - 180.0


def decode_route_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google encoded polyline without adding a runtime dependency."""
    if len(encoded) > MAX_ENCODED_POLYLINE_CHARS:
        raise ValueError("Encoded route polyline is too large")
    coordinates: list[tuple[float, float]] = []
    latitude = longitude = index = 0
    while index < len(encoded):
        deltas: list[int] = []
        for _ in range(2):
            result = shift = 0
            while True:
                if index >= len(encoded):
                    raise ValueError("Truncated encoded route polyline")
                value = ord(encoded[index]) - 63
                index += 1
                if not 0 <= value <= 0x3F:
                    raise ValueError("Encoded route polyline contains invalid characters")
                result |= (value & 0x1F) << shift
                shift += 5
                if shift >= 30 and value >= 0x20:
                    raise ValueError("Encoded route polyline contains an oversized coordinate delta")
                if value < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        latitude += deltas[0]
        longitude += deltas[1]
        point = (latitude / 100_000, longitude / 100_000)
        if not (-90 <= point[0] <= 90 and -180 <= point[1] <= 180):
            raise ValueError("Encoded route polyline contains invalid coordinates")
        coordinates.append(point)
    if len(coordinates) < 2:
        raise ValueError("A route polyline requires at least two points")
    return coordinates


def route_geometry(route: RouteDetails) -> list[tuple[float, float]]:
    """Return decoded provider geometry, or no geometry when it is invalid."""
    try:
        return decode_route_polyline(route.polyline)
    except ValueError:
        return []


def point_along_route(points: list[tuple[float, float]], fraction: float) -> tuple[float, float]:
    """Interpolate by cumulative route distance rather than endpoint midpoint."""
    if len(points) < 2:
        raise ValueError("Route geometry requires at least two points")
    segment_lengths = [_distance_m(start, end) for start, end in zip(points, points[1:])]
    target = sum(segment_lengths) * max(0.0, min(1.0, fraction))
    travelled = 0.0
    for (start, end), length in zip(zip(points, points[1:]), segment_lengths):
        if travelled + length >= target:
            ratio = 0.0 if length == 0 else (target - travelled) / length
            longitude = start[1] + _longitude_delta(start[1], end[1]) * ratio
            return (start[0] + (end[0] - start[0]) * ratio, _normalize_longitude(longitude))
        travelled += length
    return points[-1]


def route_search_points(route: RouteDetails, target_fraction: float, limit: int = 2) -> list[tuple[float, float]]:
    """Return a bounded set of search centres sampled from actual route geometry."""
    points = route_geometry(route)
    if len(points) < 2:
        return []
    fractions = [target_fraction, 0.85 if target_fraction < 0.7 else 0.5]
    return [point_along_route(points, fraction) for fraction in fractions[:limit]]


def route_place_metrics(route: RouteDetails, latitude: float, longitude: float) -> tuple[float, float]:
    """Return shortest metres to the route and fractional position along it."""
    points = route_geometry(route)
    if len(points) < 2 or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return float("inf"), 0.0
    segment_lengths = [_distance_m(start, end) for start, end in zip(points, points[1:])]
    total = max(sum(segment_lengths), 1.0)
    best_distance, best_position = float("inf"), 0.0
    travelled = 0.0
    for (start, end), length in zip(zip(points, points[1:]), segment_lengths):
        reference_latitude = math.radians((start[0] + end[0] + latitude) / 3)
        scale_x = 111_320 * math.cos(reference_latitude)
        scale_y = 110_540
        segment_x = _longitude_delta(start[1], end[1]) * scale_x
        segment_y = (end[0] - start[0]) * scale_y
        point_x = _longitude_delta(start[1], longitude) * scale_x
        point_y = (latitude - start[0]) * scale_y
        denominator = segment_x * segment_x + segment_y * segment_y
        projection = 0.0 if denominator == 0 else max(0.0, min(1.0, (point_x * segment_x + point_y * segment_y) / denominator))
        distance = math.hypot(point_x - projection * segment_x, point_y - projection * segment_y)
        if distance < best_distance:
            best_distance = distance
            best_position = (travelled + projection * length) / total
        travelled += length
    return best_distance, best_position


def facility_corridor_meters(route: RouteDetails) -> float:
    minimum = MIN_RUNNING_FACILITY_CORRIDOR_METERS if route.travel_mode == "walking" else MIN_CYCLING_FACILITY_CORRIDOR_METERS
    return min(ROUTE_CORRIDOR_METERS, max(minimum, route.distance_m * FACILITY_CORRIDOR_ROUTE_RATIO))


def select_route_places(route: RouteDetails, places: list[Any], target_fraction: float, limit: int = 3) -> list[Any]:
    """Filter and rank provider places by route proximity and requested position."""
    corridor = facility_corridor_meters(route)
    ranked: list[tuple[float, float, str, Any]] = []
    for place in places:
        latitude, longitude = getattr(place, "latitude", None), getattr(place, "longitude", None)
        if latitude is None or longitude is None:
            continue
        distance, position = route_place_metrics(route, float(latitude), float(longitude))
        if distance > corridor:
            continue
        ranked.append((distance / corridor + abs(position - target_fraction), distance, str(getattr(place, "place_id", "")), place))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in ranked[:limit]]


def waypoint_detour_ratio(origin: RouteLocation, destination: RouteLocation, waypoint: RouteWaypoint) -> float:
    """Return the waypoint's straight-line detour relative to the endpoint pair."""
    if any(value is None for value in (origin.latitude, origin.longitude, destination.latitude, destination.longitude)):
        return float("inf")
    direct = max(_distance_m((origin.latitude, origin.longitude), (destination.latitude, destination.longitude)), 1.0)
    via_waypoint = (
        _distance_m((origin.latitude, origin.longitude), (waypoint.latitude, waypoint.longitude))
        + _distance_m((waypoint.latitude, waypoint.longitude), (destination.latitude, destination.longitude))
    )
    return max(0.0, (via_waypoint - direct) / direct)


def waypoint_is_near_route(origin: RouteLocation, destination: RouteLocation, waypoint: RouteWaypoint) -> bool:
    """Bound automatic stops to a corridor around the requested A-to-B journey."""
    if any(value is None for value in (origin.latitude, origin.longitude, destination.latitude, destination.longitude)):
        return False
    start, end = (origin.latitude, origin.longitude), (destination.latitude, destination.longitude)
    x1, y1 = start[1], start[0]
    x2, y2 = end[1], end[0]
    t = max(0.0, min(1.0, ((waypoint.longitude - x1) * (x2 - x1) + (waypoint.latitude - y1) * (y2 - y1)) / max((x2 - x1) ** 2 + (y2 - y1) ** 2, 1e-12)))
    projected = (y1 + t * (y2 - y1), x1 + t * (x2 - x1))
    perpendicular = _distance_m((waypoint.latitude, waypoint.longitude), projected)
    return perpendicular <= ROUTE_CORRIDOR_METERS and waypoint_detour_ratio(origin, destination, waypoint) <= MAX_AUTOMATIC_WAYPOINT_DETOUR


def is_explicit_waypoint_query(query: str) -> bool:
    """Recognize named stops separately from generic model/place-search requests."""
    return not _GENERIC_WAYPOINT_QUERY.search(query.strip())


def select_waypoints(origin: RouteLocation, destination: RouteLocation, hotspots: list[dict[str, Any]]) -> list[RouteWaypoint]:
    """Select at most two high-activity cells near the straight-line route."""
    if origin.latitude is None or origin.longitude is None or destination.latitude is None or destination.longitude is None:
        return []
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
        if perpendicular > ROUTE_CORRIDOR_METERS or detour > MAX_AUTOMATIC_WAYPOINT_DETOUR:
            continue
        score = value / max_value - min(perpendicular / ROUTE_CORRIDOR_METERS, 1.0) * 0.5 - min(detour / MAX_AUTOMATIC_WAYPOINT_DETOUR, 1.0) * 0.5
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

    async def _compute_route(self, origin: RouteLocation, destination: RouteLocation, waypoints: list[RouteWaypoint], travel_mode: Literal["BICYCLE", "WALK"] = "BICYCLE") -> RouteDetails:
        if not self.api_key:
            raise ProviderUnavailableError("Google Routes", "API key is not configured")
        body = {"origin": self._endpoint(origin), "destination": self._endpoint(destination), "intermediates": [{"location": {"latLng": {"latitude": point.latitude, "longitude": point.longitude}}} for point in waypoints], "travelMode": travel_mode, "polylineQuality": "OVERVIEW", "polylineEncoding": "ENCODED_POLYLINE"}
        headers = {"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline,routes.legs.startLocation,routes.legs.endLocation", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(self.url, json=body, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("Google Routes", "HTTP request failed") from exc
        routes = response.json().get("routes", [])
        if not routes:
            raise ProviderPayloadError("Google Routes", f"No {travel_mode.lower()} route returned")
        route = routes[0]
        polyline = route.get("polyline", {}).get("encodedPolyline")
        duration = route.get("duration", "")
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)s", str(duration))
        if not polyline or not match or float(route.get("distanceMeters", 0)) <= 0 or float(match.group(1)) <= 0:
            raise ProviderPayloadError("Google Routes", f"Google Routes API returned an invalid {travel_mode.lower()} route")
        try:
            decode_route_polyline(polyline)
        except ValueError as exc:
            raise ProviderPayloadError("Google Routes", f"Google Routes API returned invalid {travel_mode.lower()} route geometry") from exc
        legs = route.get("legs", [])
        start = (legs[0].get("startLocation") or {}).get("latLng") if legs else None
        end = (legs[-1].get("endLocation") or {}).get("latLng") if legs else None
        if origin.latitude is None and start:
            origin = origin.model_copy(update={"latitude": float(start["latitude"]), "longitude": float(start["longitude"])})
        if destination.latitude is None and end:
            destination = destination.model_copy(update={"latitude": float(end["latitude"]), "longitude": float(end["longitude"])})
        if origin.latitude is None or origin.longitude is None or destination.latitude is None or destination.longitude is None:
            raise ProviderPayloadError("Google Routes", "route endpoint coordinates were missing from the validated response")
        mode = "bicycle" if travel_mode == "BICYCLE" else "walking"
        warning = "Bicycle routes are beta and may not include every suitable bicycle path; verify locally before travel." if mode == "bicycle" else "Running routes use Google walking geometry as a safe planning approximation; verify surfaces, crossings, and conditions locally."
        return RouteDetails(travel_mode=mode, distance_m=int(route["distanceMeters"]), duration_seconds=float(match.group(1)), polyline=polyline, origin=origin, destination=destination, waypoints=waypoints, attribution_title="Google Routes API", attribution_url="https://developers.google.com/maps/documentation/routes", warning=warning)

    async def compute_bicycle_route(self, origin: RouteLocation, destination: RouteLocation, waypoints: list[RouteWaypoint]) -> RouteDetails:
        return await self._compute_route(origin, destination, waypoints, "BICYCLE")

    async def compute_walking_route(self, origin: RouteLocation, destination: RouteLocation, waypoints: list[RouteWaypoint]) -> RouteDetails:
        return await self._compute_route(origin, destination, waypoints, "WALK")
