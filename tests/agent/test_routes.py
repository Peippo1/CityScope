from __future__ import annotations

import asyncio
import pytest

from apps.api.app.agent.route_service import (
    GoogleRoutesService,
    RouteDetails,
    RouteLocation,
    RouteWaypoint,
    decode_route_polyline,
    facility_corridor_meters,
    is_explicit_waypoint_query,
    route_place_metrics,
    route_search_points,
    select_route_places,
    waypoint_detour_ratio,
    waypoint_is_near_route,
    select_waypoints,
)
from apps.api.app.agent.schemas import PlaceResult


def encode_polyline(points: list[tuple[float, float]]) -> str:
    encoded: list[str] = []
    previous_latitude = previous_longitude = 0
    for latitude, longitude in points:
        current_latitude = round(latitude * 100_000)
        current_longitude = round(longitude * 100_000)
        for delta in (current_latitude - previous_latitude, current_longitude - previous_longitude):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                encoded.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            encoded.append(chr(value + 63))
        previous_latitude, previous_longitude = current_latitude, current_longitude
    return "".join(encoded)


def route_details(points: list[tuple[float, float]], *, mode: str = "bicycle", distance_m: int = 5000) -> RouteDetails:
    return RouteDetails(
        travel_mode=mode,
        distance_m=distance_m,
        duration_seconds=1200,
        polyline=encode_polyline(points),
        origin=RouteLocation(name="Origin", latitude=points[0][0], longitude=points[0][1]),
        destination=RouteLocation(name="Destination", latitude=points[-1][0], longitude=points[-1][1]),
    )


def place(place_id: str, latitude: float, longitude: float) -> PlaceResult:
    return PlaceResult(place_id=place_id, name=place_id, latitude=latitude, longitude=longitude, category="cafe", h3_cell="test")


def test_waypoint_selection_is_bounded_and_deterministic() -> None:
    origin = RouteLocation(name="Origin", latitude=51.50, longitude=-0.14)
    destination = RouteLocation(name="Destination", latitude=51.51, longitude=-0.08)
    cells = [
        {"h3_cell": "89194ad3353ffff", "value": 100},
        {"h3_cell": "89194ad3203ffff", "value": 90},
        {"h3_cell": "89194ad32cbffff", "value": 80},
    ]
    first = select_waypoints(origin, destination, cells)
    second = select_waypoints(origin, destination, cells)
    assert [item.h3_cell for item in first] == [item.h3_cell for item in second]
    assert len(first) <= 2


def test_generic_waypoint_queries_are_not_treated_as_explicit_places() -> None:
    assert not is_explicit_waypoint_query("a café halfway")
    assert not is_explicit_waypoint_query("find a cafe nearby")
    assert is_explicit_waypoint_query("Foundry Coffee")


def test_waypoint_corridor_rejects_extreme_detours_but_allows_nearby_stops() -> None:
    origin = RouteLocation(name="King's Cross", latitude=51.5316, longitude=-0.1236)
    destination = RouteLocation(name="Camden", latitude=51.5390, longitude=-0.1426)
    nearby = RouteWaypoint(h3_cell="near", latitude=51.535, longitude=-0.132, mobility_value=0, score=1, reason="test")
    distant = RouteWaypoint(h3_cell="far", latitude=51.4408, longitude=0.0876, mobility_value=0, score=1, reason="test")

    assert waypoint_is_near_route(origin, destination, nearby)
    assert not waypoint_is_near_route(origin, destination, distant)
    assert waypoint_detour_ratio(origin, destination, distant) > 0.75


def test_route_distance_validation_uses_waypoint_detour_not_global_distance() -> None:
    origin = RouteLocation(name="A", latitude=51.50, longitude=-0.14)
    destination = RouteLocation(name="B", latitude=51.51, longitude=-0.08)
    nearby = RouteWaypoint(h3_cell="near", latitude=51.505, longitude=-0.11, mobility_value=0, score=1, reason="test")
    assert waypoint_detour_ratio(origin, destination, nearby) < 0.75


def test_route_search_samples_distance_along_curved_geometry() -> None:
    route = route_details([(51.50, -0.14), (51.52, -0.14), (51.52, -0.08)])

    midpoint = route_search_points(route, 0.5, limit=1)[0]

    assert midpoint[0] == pytest.approx(51.52, abs=0.001)
    assert midpoint[1] == pytest.approx(-0.126, abs=0.002)


def test_route_search_and_distance_wrap_across_the_international_date_line() -> None:
    route = route_details([(0.0, 179.9), (0.0, -179.9)], distance_m=22_264)

    midpoint = route_search_points(route, 0.5, limit=1)[0]
    distance, position = route_place_metrics(route, 0.001, 180.0)

    assert abs(abs(midpoint[1]) - 180.0) < 0.001
    assert distance == pytest.approx(110, abs=10)
    assert position == pytest.approx(0.5, abs=0.01)


def test_route_place_ranking_prefers_requested_position_then_proximity() -> None:
    route = route_details([(51.50, -0.14), (51.50, -0.10), (51.50, -0.06)])
    halfway = place("halfway", 51.5010, -0.10)
    near_finish = place("near-finish", 51.5002, -0.065)

    assert [item.place_id for item in select_route_places(route, [near_finish, halfway], 0.5)] == ["halfway", "near-finish"]
    assert [item.place_id for item in select_route_places(route, [halfway, near_finish], 0.85)] == ["near-finish", "halfway"]


@pytest.mark.parametrize("points", [
    [(51.53, -0.12), (51.54, -0.14)],
    [(51.50, -0.20), (51.49, -0.16)],
    [(51.57, -0.30), (51.58, -0.25)],
])
def test_same_unrelated_cafe_is_rejected_for_unrelated_london_routes(points) -> None:
    route = route_details(points)
    cafe_pedlar = place("cafe-pedlar", 51.4620, -0.0670)

    assert select_route_places(route, [cafe_pedlar], 0.5) == []


def test_facility_corridor_scales_by_mode_and_route_length_but_remains_bounded() -> None:
    short_running = route_details([(51.50, -0.14), (51.51, -0.13)], mode="walking", distance_m=2000)
    short_cycling = route_details([(51.50, -0.14), (51.51, -0.13)], distance_m=2000)
    long_cycling = route_details([(51.50, -0.14), (51.60, -0.04)], distance_m=100_000)

    assert facility_corridor_meters(short_running) == 250
    assert facility_corridor_meters(short_cycling) == 500
    assert facility_corridor_meters(long_cycling) == 3000


def test_route_place_metrics_report_candidate_distance_and_position() -> None:
    route = route_details([(51.50, -0.14), (51.50, -0.10), (51.50, -0.06)])

    distance, position = route_place_metrics(route, 51.501, -0.10)

    assert distance == pytest.approx(110, abs=10)
    assert position == pytest.approx(0.5, abs=0.02)


def test_route_discovery_rejects_candidates_when_provider_geometry_is_invalid() -> None:
    route = RouteDetails(
        travel_mode="bicycle",
        distance_m=2000,
        duration_seconds=600,
        polyline="not-a-valid-polyline",
        origin=RouteLocation(name="Origin", latitude=51.50, longitude=-0.14),
        destination=RouteLocation(name="Destination", latitude=51.51, longitude=-0.10),
    )

    assert route_search_points(route, 0.5) == []
    assert select_route_places(route, [place("near-endpoint", 51.505, -0.12)], 0.5) == []


def test_polyline_decoder_rejects_characters_outside_google_encoding_range() -> None:
    with pytest.raises(ValueError, match="invalid characters"):
        decode_route_polyline("!!")


def test_routes_request_is_bicycle_and_uses_place_ids(monkeypatch) -> None:
    captured = {}

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"routes": [{"distanceMeters": 2400, "duration": "900s", "polyline": {"encodedPolyline": encode_polyline([(51.5, -0.1), (51.51, -0.09)])}}]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, json, headers): captured.update(url=url, json=json, headers=headers); return Response()

    monkeypatch.setattr("apps.api.app.agent.route_service.httpx.AsyncClient", lambda **kwargs: Client())
    origin = RouteLocation(name="Origin", place_id="ChIJorigin", latitude=51.5, longitude=-0.1)
    destination = RouteLocation(name="Destination", place_id="ChIJdestination", latitude=51.51, longitude=-0.09)
    waypoint = RouteWaypoint(h3_cell="89194ad3353ffff", latitude=51.505, longitude=-0.095, mobility_value=5, score=1, reason="test")
    result = asyncio.run(GoogleRoutesService(api_key="secret").compute_bicycle_route(origin, destination, [waypoint]))
    assert captured["json"]["travelMode"] == "BICYCLE"
    assert captured["json"]["origin"] == {"placeId": "ChIJorigin"}
    assert captured["json"]["destination"] == {"placeId": "ChIJdestination"}
    assert captured["json"]["intermediates"][0]["location"]["latLng"]["latitude"] == waypoint.latitude
    assert "routes.polyline.encodedPolyline" in captured["headers"]["X-Goog-FieldMask"]
    assert result.polyline == encode_polyline([(51.5, -0.1), (51.51, -0.09)])


def test_routes_request_supports_running_as_walking_geometry(monkeypatch) -> None:
    captured = {}

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"routes": [{"distanceMeters": 10000, "duration": "3600s", "polyline": {"encodedPolyline": encode_polyline([(40.7, -73.99), (40.66, -73.97)])}}]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, json, headers): captured.update(json=json); return Response()

    monkeypatch.setattr("apps.api.app.agent.route_service.httpx.AsyncClient", lambda **kwargs: Client())
    origin = RouteLocation(name="DUMBO", latitude=40.7, longitude=-73.99)
    destination = RouteLocation(name="Prospect Park", latitude=40.66, longitude=-73.97)
    result = asyncio.run(GoogleRoutesService(api_key="secret").compute_walking_route(origin, destination, []))
    assert captured["json"]["travelMode"] == "WALK"
    assert result.travel_mode == "walking"


def test_place_id_route_hydrates_endpoint_coordinates_from_routes_response(monkeypatch) -> None:
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"routes": [{"distanceMeters": 2400, "duration": "900s", "polyline": {"encodedPolyline": encode_polyline([(51.53, -0.12), (51.54, -0.14)])}, "legs": [{"startLocation": {"latLng": {"latitude": 51.53, "longitude": -0.12}}, "endLocation": {"latLng": {"latitude": 51.54, "longitude": -0.14}}}]}]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, json, headers):
            assert json["origin"] == {"placeId": "ChIJorigin"}
            return Response()

    monkeypatch.setattr("apps.api.app.agent.route_service.httpx.AsyncClient", lambda **kwargs: Client())
    origin = RouteLocation(name="King's Cross", place_id="ChIJorigin")
    destination = RouteLocation(name="Camden", place_id="ChIJdestination")
    result = asyncio.run(GoogleRoutesService(api_key="secret").compute_bicycle_route(origin, destination, []))
    assert result.origin.latitude == 51.53
    assert result.destination.longitude == -0.14


def test_routes_rejects_missing_geometry(monkeypatch) -> None:
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"routes": [{"distanceMeters": 2400, "duration": "900s", "polyline": {}}]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, json, headers): return Response()

    monkeypatch.setattr("apps.api.app.agent.route_service.httpx.AsyncClient", lambda **kwargs: Client())
    origin = RouteLocation(name="Origin", latitude=51.5, longitude=-0.1)
    destination = RouteLocation(name="Destination", latitude=51.51, longitude=-0.09)
    with pytest.raises(RuntimeError, match="invalid bicycle route"):
        asyncio.run(GoogleRoutesService(api_key="test").compute_bicycle_route(origin, destination, []))


def test_routes_rejects_malformed_encoded_geometry(monkeypatch) -> None:
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"routes": [{"distanceMeters": 2400, "duration": "900s", "polyline": {"encodedPolyline": "!!"}}]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, json, headers): return Response()

    monkeypatch.setattr("apps.api.app.agent.route_service.httpx.AsyncClient", lambda **kwargs: Client())
    origin = RouteLocation(name="Origin", latitude=51.5, longitude=-0.1)
    destination = RouteLocation(name="Destination", latitude=51.51, longitude=-0.09)

    with pytest.raises(RuntimeError, match="invalid bicycle route geometry"):
        asyncio.run(GoogleRoutesService(api_key="test").compute_bicycle_route(origin, destination, []))
