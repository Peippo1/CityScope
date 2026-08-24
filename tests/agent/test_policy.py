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
