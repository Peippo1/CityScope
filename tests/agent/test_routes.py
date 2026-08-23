from __future__ import annotations

import asyncio

from apps.api.app.agent.route_service import GoogleRoutesService, RouteLocation, RouteWaypoint, select_waypoints


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
