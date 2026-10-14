from __future__ import annotations

import asyncio
import pytest

from apps.api.app.agent.route_service import (
    GoogleRoutesService,
    RouteLocation,
    RouteWaypoint,
    is_explicit_waypoint_query,
    waypoint_detour_ratio,
    waypoint_is_near_route,
    select_waypoints,
)


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


def test_routes_request_is_bicycle_and_uses_place_ids(monkeypatch) -> None:
    captured = {}

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"routes": [{"distanceMeters": 2400, "duration": "900s", "polyline": {"encodedPolyline": "abc"}}]}

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
    assert result.polyline == "abc"


def test_routes_request_supports_running_as_walking_geometry(monkeypatch) -> None:
    captured = {}

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"routes": [{"distanceMeters": 10000, "duration": "3600s", "polyline": {"encodedPolyline": "run"}}]}

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
        def json(self): return {"routes": [{"distanceMeters": 2400, "duration": "900s", "polyline": {"encodedPolyline": "abc"}, "legs": [{"startLocation": {"latLng": {"latitude": 51.53, "longitude": -0.12}}, "endLocation": {"latLng": {"latitude": 51.54, "longitude": -0.14}}}]}]}

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
