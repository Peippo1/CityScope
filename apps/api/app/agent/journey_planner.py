"""Focused orchestration for validated outbound/return ride or run segments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .route_service import RouteDetails, RouteExecutor, RouteLocation, RouteWaypoint


@dataclass(frozen=True)
class JourneySegments:
    outbound: RouteDetails
    return_route: RouteDetails | None = None
    used_direct_fallback: bool = False


class JourneyPlanner:
    """Keep route-call budgeting and fallback semantics out of the API service."""

    def __init__(self, executor: RouteExecutor, reserve_call: Callable[[], bool]):
        self.executor = executor
        self.reserve_call = reserve_call

    async def plan(self, origin: RouteLocation, destination: RouteLocation, waypoints: list[RouteWaypoint], return_to_origin: bool, travel_mode: str = "bicycle") -> JourneySegments | None:
        route = None
        used_direct_fallback = False
        attempts = (waypoints, []) if waypoints else ([],)
        for points in attempts:
            if not self.reserve_call():
                break
            try:
                compute = self.executor.compute_walking_route if travel_mode == "walking" else self.executor.compute_bicycle_route
                route = await compute(origin, destination, points)
                used_direct_fallback = points == [] and bool(waypoints)
                break
            except Exception:
                continue
        if route is None:
            return None
        return_route = None
        if return_to_origin and self.reserve_call():
            try:
                compute = self.executor.compute_walking_route if travel_mode == "walking" else self.executor.compute_bicycle_route
                return_route = await compute(destination, origin, [])
            except Exception:
                return_route = None
        return JourneySegments(route, return_route, used_direct_fallback)
