from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

import h3
from pydantic import BaseModel

from .places import MAX_MAPS_SEARCH_CALLS, AmenitySearchPlan
from .schemas import InvestigationRequest, ToolDecision
from ..cities import get_city


class PolicyOutcome(StrEnum):
    ALLOW = "allow"
    REJECT = "reject"
    PARTIAL = "partial"
    FAIL = "fail"


class PolicyCode(StrEnum):
    ALLOWED = "allowed"
    UNSUPPORTED_WEATHER = "unsupported_weather"
    UNSUPPORTED_DOMAIN = "unsupported_domain"
    UNSUPPORTED_CITY = "unsupported_city"
    UNSUPPORTED_TOOL = "unsupported_tool"
    TOOL_ROUND_LIMIT = "tool_round_limit"
    CITY_DATA_CALL_LIMIT = "city_data_call_limit"
    MAPS_CALL_LIMIT = "maps_call_limit"
    ROUTES_CALL_LIMIT = "routes_call_limit"
    MAPS_REQUIRES_TRUSTED_H3 = "maps_requires_trusted_h3"
    UNTRUSTED_H3 = "untrusted_h3"
    INVALID_ROUTE_INTENT = "invalid_route_intent"
    MODEL_COORDINATES_FORBIDDEN = "model_coordinates_forbidden"
    ROUTE_WAYPOINT_LIMIT = "route_waypoint_limit"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNSAFE_RESPONSE = "unsafe_response"


class PolicyDecision(BaseModel):
    outcome: PolicyOutcome
    code: PolicyCode
    message: str


@dataclass
class ExecutionBudget:
    model_rounds: int = 0
    city_data_calls: int = 0
    maps_calls: int = 0
    routes_calls: int = 0


class GuardrailPolicy:
    max_model_rounds = 3
    max_city_data_calls = 3
    max_maps_calls = MAX_MAPS_SEARCH_CALLS
    max_routes_calls = 2
    max_route_waypoints = 2
    allowed_tools = {
        "describe_dataset", "get_area_metrics", "find_hotspots", "compare_areas",
        "maps.search_places", "route.intent",
    }
    weather_terms = {"weather", "forecast", "temperature", "rain", "rainfall", "wind"}
    unsupported_terms = {"revenue", "population", "demographics", "crime"}
    _secret_pattern = re.compile(r"(?i)(api[_-]?key|authorization|bearer|credential|secret|token)\s*[:=]\s*\S+")

    @staticmethod
    def allow() -> PolicyDecision:
        return PolicyDecision(outcome=PolicyOutcome.ALLOW, code=PolicyCode.ALLOWED, message="Allowed by CityScope policy.")

    def check_request(self, request: InvestigationRequest) -> PolicyDecision:
        try:
            city = get_city(request.city)
        except ValueError:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.UNSUPPORTED_CITY, message="CityScope does not support this city.")
        words = set(re.findall(r"[a-z]+", request.question.lower()))
        if words & self.weather_terms:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.UNSUPPORTED_WEATHER, message="Weather is outside the current CityScope investigation boundary.")
        if words & self.unsupported_terms:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.UNSUPPORTED_DOMAIN, message="This question is outside the supported CityScope investigation scope.")
        return self.allow()

    def check_route_locations(self, city_id: str, locations: Iterable[Any]) -> PolicyDecision:
        city = get_city(city_id)
        if not city.routes:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.INVALID_ROUTE_INTENT, message=f"Bicycle routing is unavailable for {city.name} in this release.")
        south, west, north, east = city.bounds
        if any(not (south <= float(location.latitude) <= north and west <= float(location.longitude) <= east) for location in locations):
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.INVALID_ROUTE_INTENT, message=f"Route endpoints must resolve within {city.name}.")
        return self.allow()

    def check_model_round(self, budget: ExecutionBudget) -> PolicyDecision:
        if budget.model_rounds >= self.max_model_rounds:
            return PolicyDecision(outcome=PolicyOutcome.FAIL, code=PolicyCode.TOOL_ROUND_LIMIT, message="The investigation exceeded its bounded planning budget.")
        budget.model_rounds += 1
        return self.allow()

    def check_model_decision(self, decision: ToolDecision) -> PolicyDecision:
        if decision.kind != "call_tool":
            return self.allow()
        if decision.tool not in self.allowed_tools:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.UNSUPPORTED_TOOL, message="The model requested an unsupported operation.")
        if decision.tool == "route.intent":
            if set(decision.arguments) - {"origin", "destination"}:
                return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.MODEL_COORDINATES_FORBIDDEN, message="Route coordinates and provider payloads must be selected by trusted backend code.")
            if not all(isinstance(decision.arguments.get(key), str) and decision.arguments[key].strip() for key in ("origin", "destination")):
                return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.INVALID_ROUTE_INTENT, message="A bicycle route requires named London origins and destinations.")
        return self.allow()

    def check_city_data_call(self, budget: ExecutionBudget) -> PolicyDecision:
        if budget.city_data_calls >= self.max_city_data_calls:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.CITY_DATA_CALL_LIMIT, message="The City Data call budget was exceeded.")
        budget.city_data_calls += 1
        return self.allow()

    def check_maps_plan(self, plan: AmenitySearchPlan, trusted_cells: Iterable[str], budget: ExecutionBudget) -> PolicyDecision:
        trusted = set(trusted_cells)
        cells = set(plan.h3_cells)
        if not trusted:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.MAPS_REQUIRES_TRUSTED_H3, message="City Data must narrow the search before Maps enrichment.")
        if any(not h3.is_valid_cell(cell) for cell in cells) or not cells.issubset(trusted):
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.UNTRUSTED_H3, message="Maps search cells must be trusted CityScope H3 cells.")
        calls = len(plan.h3_cells) * len(plan.categories)
        if calls > self.max_maps_calls or budget.maps_calls + calls > self.max_maps_calls:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.MAPS_CALL_LIMIT, message="The Maps search call budget was exceeded.")
        budget.maps_calls += calls
        return self.allow()

    def reserve_route_resolution(self, budget: ExecutionBudget) -> PolicyDecision:
        if budget.maps_calls + 2 > self.max_maps_calls:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.MAPS_CALL_LIMIT, message="The Maps search call budget was exceeded.")
        budget.maps_calls += 2
        return self.allow()

    def check_waypoints(self, waypoints: list[Any]) -> PolicyDecision:
        if len(waypoints) > self.max_route_waypoints:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.ROUTE_WAYPOINT_LIMIT, message="A route may contain at most two trusted waypoints.")
        return self.allow()

    def reserve_route_call(self, budget: ExecutionBudget) -> PolicyDecision:
        if budget.routes_calls >= self.max_routes_calls:
            return PolicyDecision(outcome=PolicyOutcome.REJECT, code=PolicyCode.ROUTES_CALL_LIMIT, message="The Routes call budget was exceeded.")
        budget.routes_calls += 1
        return self.allow()

    def provider_error(self, provider: str, *, partial: bool = False) -> PolicyDecision:
        return PolicyDecision(
            outcome=PolicyOutcome.PARTIAL if partial else PolicyOutcome.FAIL,
            code=PolicyCode.PROVIDER_UNAVAILABLE,
            message=f"{provider} was unavailable for this request.",
        )

    def validate_public_result(self, result: Any) -> PolicyDecision:
        serialized = result.model_dump_json() if hasattr(result, "model_dump_json") else str(result)
        known_secrets = [os.getenv(name) for name in ("GEMINI_API_KEY", "GOOGLE_MAPS_GROUNDING_API_KEY", "GOOGLE_ROUTES_API_KEY", "GOOGLE_MAPS_API_KEY")]
        if self._secret_pattern.search(serialized) or any(value and len(value) >= 8 and value in serialized for value in known_secrets):
            return PolicyDecision(outcome=PolicyOutcome.FAIL, code=PolicyCode.UNSAFE_RESPONSE, message="The result failed the response safety check.")
        return self.allow()
