from __future__ import annotations

import asyncio

import pytest

from apps.api.app.agent.adk_runtime import ADKInvestigationModel, _bounded_tool, build_root_agent, heuristic_route_decision
from apps.api.app.agent.model import GemmaJourneyCharacterScorer, JourneyCharacterScore


def test_root_agent_is_optional_when_adk_is_not_installed() -> None:
    # The local test image may omit ADK; production installs the pinned extra.
    agent = build_root_agent()
    assert agent is None or getattr(agent, "name", "") == "cityscope_taskmaster"


def test_adk_model_preserves_typed_fallback_without_adk(monkeypatch) -> None:
    monkeypatch.setattr("apps.api.app.agent.adk_runtime.build_root_agent", lambda: None)
    class FakeFallback:
        model_name = "gemini-3.5-flash"

        async def decide(self, question, context, tool_results):
            from apps.api.app.agent.schemas import ToolDecision
            return ToolDecision(kind="answer", answer="ok")

    result = asyncio.run(ADKInvestigationModel(fallback=FakeFallback()).decide("q", "{}", []))
    assert result.answer == "ok"


def test_bounded_tool_never_executes_a_provider_call() -> None:
    tool = _bounded_tool("maps.search_places")
    assert tool.__name__ == "maps_search_places"
    assert "delegated_to_deterministic_application" in tool("secret-free request")


@pytest.mark.parametrize(("question", "origin", "destination"), [
    ("Cycle from King's Cross to Camden with coffee", "King'S Cross", "Camden"),
    ("Run around Hyde Park for 45 minutes", "Hyde Park", "Kensington Gardens"),
    ("Bike from Central Park with food", "Central Park", "Prospect Park"),
])
def test_route_fallback_keeps_named_demo_endpoints(question, origin, destination):
    decision = heuristic_route_decision(question)
    assert decision.arguments["origin"] == origin
    assert decision.arguments["destination"] == destination


def test_gemma_score_schema_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError):
        JourneyCharacterScore(scenic=11, green=1, lively=1, cultural=1, relaxed=1, coffee=1, rationale="x")


def test_gemma_scorer_requires_a_server_key(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        asyncio.run(GemmaJourneyCharacterScorer(api_key=None).score("scenic route", "evidence"))
