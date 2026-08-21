from __future__ import annotations

import json
import uuid
from typing import Any

from services.city_data_mcp.schemas import DatasetMetadata, ToolEnvelope

from .mcp_client import CityDataMcpClient
from .model import GeminiInvestigationModel, InvestigationModel
from .schemas import InvestigationRequest, InvestigationResult, TraceEvent, ToolDecision

MAX_TOOL_ROUNDS = 3
ALLOWED_TOOLS = {"describe_dataset", "get_area_metrics", "find_hotspots", "compare_areas"}


class InvestigationService:
    def __init__(self, mcp_client: CityDataMcpClient | Any | None = None, model: InvestigationModel | None = None) -> None:
        self.mcp_client = mcp_client or CityDataMcpClient()
        self.model = model or GeminiInvestigationModel()

    async def investigate(self, request: InvestigationRequest) -> InvestigationResult:
        investigation_id = str(uuid.uuid4())
        trace = [TraceEvent(kind="planning", label="Classify question and select a City Data MCP tool", status="completed")]
        context = request.context.model_dump_json()
        tool_results: list[dict] = []
        envelope: ToolEnvelope | None = None
        final_decision: ToolDecision | None = None

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                decision = await self.model.decide(request.question, context, tool_results)
            except Exception as exc:
                trace.append(TraceEvent(kind="planning", label="Model decision failed", status="failed"))
                return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The investigation could not be planned.", limitations=[str(exc)], trace=trace)
            final_decision = decision
            if decision.kind == "unsupported":
                return InvestigationResult(investigation_id=investigation_id, status="unsupported", answer=decision.answer or "I can answer historical London mobility questions about the available dataset, hotspots, H3 metrics, and area comparisons.", limitations=["This question is outside the supported CityScope V1 investigation scope."], trace=trace, follow_up_suggestions=decision.follow_up_suggestions)
            if decision.kind == "answer":
                break
            if decision.tool not in ALLOWED_TOOLS:
                trace.append(TraceEvent(kind="tool_call", label="Rejected unsupported tool", status="rejected", tool=decision.tool))
                return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The investigation requested an unsupported data operation.", limitations=["Only the four City Data MCP tools are available in V1."], trace=trace)
            try:
                envelope_data = await self.mcp_client.call(decision.tool, decision.arguments)
                if decision.tool == "describe_dataset":
                    dataset = DatasetMetadata.model_validate(envelope_data)
                    envelope = ToolEnvelope(dataset=dataset, results=[], evidence=[], map_layers=[], limitations=dataset.limitations)
                else:
                    envelope = ToolEnvelope.model_validate(envelope_data)
                tool_results.append(envelope.model_dump(mode="json"))
                trace.append(TraceEvent(kind="tool_call", label=f"Called City Data MCP: {decision.tool}", status="completed", tool=decision.tool, result_count=len(envelope.results)))
            except Exception as exc:
                trace.append(TraceEvent(kind="tool_call", label=f"City Data MCP call failed: {decision.tool}", status="failed", tool=decision.tool))
                return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The City Data MCP service could not answer this investigation.", limitations=[str(exc)], trace=trace)
            context = json.dumps({"request": request.context.model_dump(mode="json"), "available_evidence": tool_results}, default=str)

        if envelope is None or final_decision is None or final_decision.kind != "answer":
            return InvestigationResult(investigation_id=investigation_id, status="failed", answer="The investigation exceeded its bounded tool-call budget.", limitations=[f"Maximum tool-call rounds: {MAX_TOOL_ROUNDS}"], trace=trace)
        trace.append(TraceEvent(kind="synthesis", label="Synthesize an evidence-grounded answer", status="completed"))
        return InvestigationResult(investigation_id=investigation_id, status="answered", answer=final_decision.answer or "No answer was returned.", dataset=envelope.dataset, evidence=envelope.evidence, map_layers=envelope.map_layers, limitations=envelope.limitations, trace=trace, follow_up_suggestions=final_decision.follow_up_suggestions)
