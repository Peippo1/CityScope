"""Small ADK runtime boundary for CityScope's Taskmaster planner.

ADK owns model execution and session lifecycle. Existing MCP clients and the
deterministic application layer remain authoritative for side effects.
"""

from __future__ import annotations

import json
import os
import uuid
import warnings
from typing import Any

from .model import GeminiInvestigationModel
from .schemas import ToolDecision


def _bounded_tool(name: str):
    """Return a safe planning tool; execution is deliberately backend-owned."""

    def tool(request: str) -> str:
        return json.dumps({"tool": name, "status": "delegated_to_deterministic_application", "request": request[:200]})

    tool.__name__ = name.replace(".", "_")
    tool.__doc__ = f"Plan a bounded {name} operation; the application executes it safely."
    return tool


def build_root_agent() -> Any | None:
    """Build the single root LlmAgent when google-adk is installed."""

    try:
        # ADK 1.14 imports optional Vertex modules that currently emit
        # deprecation warnings during import; keep that upstream noise out of
        # the API/test warning policy without suppressing runtime failures.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from google.adk.agents import LlmAgent
    except ImportError:
        return None
    # ADK's Gemini backend reads GOOGLE_API_KEY; keep the existing server-only
    # CityScope credential name as the source of truth.
    if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
    return LlmAgent(
        name="cityscope_taskmaster",
        model=os.getenv("CITYSCOPE_GEMINI_MODEL", "gemini-3.5-flash"),
        instruction=(
            "You are the CityScope Taskmaster root agent. Plan one bounded next action at a time, "
            "then return the requested ToolDecision JSON. MCP and Maps are external tool boundaries; "
            "the application, not the model, executes Routes, waypoints, validation, and provenance. "
            "Never expose secrets or construct a Routes API request. Return only JSON with keys "
            "kind, tool, arguments, answer, and follow_up_suggestions; tool must be one of "
            "describe_dataset, get_area_metrics, find_hotspots, compare_areas, compare_cities, "
            "maps.search_places, or route.intent. For route.intent, extract named origin and destination, "
            "return_to_origin for loops, travel_mode bicycle or walking for running, bounded requested_stops, preferences, and an optional template_id; never emit coordinates or polylines."
        ),
        tools=[
            _bounded_tool("inspect_city_capabilities"),
            _bounded_tool("city_data.find_hotspots"),
            _bounded_tool("city_live_data.get_live_station_status"),
            _bounded_tool("maps.search_places"),
            _bounded_tool("route.intent"),
            _bounded_tool("journey_character.score"),
        ],
    )


class ADKInvestigationModel:
    """InvestigationModel adapter backed by an ADK Runner with safe fallback."""

    def __init__(self, fallback: GeminiInvestigationModel | None = None) -> None:
        self.fallback = fallback or GeminiInvestigationModel()
        self.model_name = self.fallback.model_name
        self._agent = build_root_agent()

    @property
    def available(self) -> bool:
        return self._agent is not None

    async def decide(self, question: str, context: str, tool_results: list[dict]) -> ToolDecision:
        if self._agent is None:
            return await self.fallback.decide(question, context, tool_results)
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.genai import types

            app_name = "cityscope"
            user_id = "cityscope-request"
            session_id = str(uuid.uuid4())
            sessions = InMemorySessionService()
            await sessions.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
            runner = Runner(agent=self._agent, app_name=app_name, session_service=sessions)
            prompt = json.dumps({"question": question, "context": context, "previous_tool_results": tool_results}, default=str)
            final_text = None
            async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=types.Content(role="user", parts=[types.Part(text=prompt)])):
                if getattr(event, "is_final_response", lambda: False)():
                    parts = getattr(getattr(event, "content", None), "parts", []) or []
                    final_text = next((part.text for part in parts if getattr(part, "text", None)), None)
            if not final_text:
                raise RuntimeError("ADK returned no final response")
            return ToolDecision.model_validate_json(final_text)
        except Exception:
            # Do not retry a provider/auth failure: the service policy will
            # surface one sanitized failure and preserve the cost budget.
            raise
