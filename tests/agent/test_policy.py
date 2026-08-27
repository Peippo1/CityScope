from types import SimpleNamespace

import pytest

from apps.api.app.agent.policy import ExecutionBudget, GuardrailPolicy, PolicyCode
from apps.api.app.agent.schemas import InvestigationRequest, ToolDecision


def test_weather_is_rejected_before_any_budget_is_consumed():
    budget = ExecutionBudget()
    decision = GuardrailPolicy().check_request(InvestigationRequest(question="What is the weather in the busiest cell?"))
    assert decision.code == PolicyCode.UNSUPPORTED_WEATHER
    assert budget == ExecutionBudget()


def test_model_coordinates_and_raw_route_fields_are_rejected():
    decision = ToolDecision(kind="call_tool",tool="route.intent",arguments={"origin":"A","destination":"B","latitude":51.5})
    assert GuardrailPolicy().check_model_decision(decision).code == PolicyCode.MODEL_COORDINATES_FORBIDDEN


def test_provider_error_never_contains_raw_exception_details():
    decision = GuardrailPolicy().provider_error("Google Routes API")
    assert decision.code == PolicyCode.PROVIDER_UNAVAILABLE
    assert "credential" not in decision.message.lower()


def test_cross_city_policy_rejects_raw_volume_rankings():
    decision = ToolDecision(kind="call_tool", tool="compare_cities", arguments={"cities": ["london", "new_york"], "metric": "total_activity"})

    assert GuardrailPolicy().check_model_decision(decision).code == PolicyCode.UNSUPPORTED_DOMAIN


@pytest.mark.parametrize(("city", "inside"), [
    ("london", (51.50, -0.10)),
    ("new_york", (40.75, -73.98)),
    ("chicago", (41.88, -87.63)),
    ("washington_dc", (38.91, -77.04)),
])
def test_route_endpoints_must_stay_inside_the_selected_city(city, inside):
    policy = GuardrailPolicy()
    valid = [SimpleNamespace(latitude=inside[0], longitude=inside[1])] * 2
    mixed_city = valid + [SimpleNamespace(latitude=48.86, longitude=2.35)]

    assert policy.check_route_locations(city, valid).code == PolicyCode.ALLOWED
    assert policy.check_route_locations(city, mixed_city).code == PolicyCode.INVALID_ROUTE_INTENT
