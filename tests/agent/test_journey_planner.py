import asyncio

from apps.api.app.agent.journey_planner import JourneyPlanner
from apps.api.app.agent.route_service import RouteDetails, RouteLocation


class Executor:
    def __init__(self):
        self.calls = []

    async def compute_bicycle_route(self, origin, destination, waypoints):
        self.calls.append((origin.name, destination.name, len(waypoints)))
        return RouteDetails(distance_m=1000, duration_seconds=300, polyline="x", origin=origin, destination=destination, waypoints=waypoints)


def test_planner_uses_one_call_without_loop_and_two_with_loop():
    origin = RouteLocation(name="A", latitude=51.5, longitude=-0.1)
    destination = RouteLocation(name="B", latitude=51.51, longitude=-0.09)
    executor = Executor()
    planner = JourneyPlanner(executor, lambda: True)
    result = asyncio.run(planner.plan(origin, destination, [], False))
    assert result and len(executor.calls) == 1

    executor.calls.clear()
    result = asyncio.run(planner.plan(origin, destination, [], True))
    assert result and result.return_route and len(executor.calls) == 2
