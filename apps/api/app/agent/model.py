from __future__ import annotations

import json
import os
from typing import Protocol

from .schemas import ToolDecision


class InvestigationModel(Protocol):
    async def decide(self, question: str, context: str, tool_results: list[dict]) -> ToolDecision:
        ...


class GeminiInvestigationModel:
    """Small structured-output adapter; tool execution remains owned by the agent."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("CITYSCOPE_GEMINI_MODEL", "gemini-2.5-flash")

    async def decide(self, question: str, context: str, tool_results: list[dict]) -> ToolDecision:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("The google-genai package is required for Gemini investigations") from exc

        client = genai.Client(api_key=self.api_key)
        prompt = f"""You are the CityScope London investigation planner.
Use only the four City Data MCP tools listed below. Never invent current or live facts.
Supported questions: historical dataset description, H3 activity hotspots, metrics for supplied H3 cells,
and comparisons between supplied H3 groups. Reject questions about cafes, weather, traffic, routes,
demographics, revenue, forecasts, unnamed areas, or other cities.
Return JSON matching the requested schema. Call at most one tool per decision.
Tools: describe_dataset(city); find_hotspots(city, metric, time_filter, limit);
get_area_metrics(city, h3_cells, metrics, time_filter); compare_areas(city, area_groups, metrics, time_filter).

Question: {question}
Context: {context}
Previous tool results: {json.dumps(tool_results, default=str)}
"""
        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": ToolDecision},
        )
        return ToolDecision.model_validate_json(response.text)

