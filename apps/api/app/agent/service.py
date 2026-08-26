from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from services.city_data_mcp.schemas import DatasetMetadata, Evidence, ToolEnvelope

from .mcp_client import CityDataMcpClient
from .live_mcp_client import CityLiveMcpClient
from .model import GeminiInvestigationModel, InvestigationModel
from .places import AmenitySearchPlan, GoogleMapsGroundingClient, deterministic_amenity_analysis, normalize_amenity_plan
from .policy import ExecutionBudget, GuardrailPolicy, PolicyCode, PolicyDecision, PolicyOutcome
from .route_service import GoogleRoutesService, RouteDetails, RouteExecutor, select_waypoints
from .schemas import InvestigationRequest, InvestigationResult, TraceEvent, ToolDecision
from .telemetry import TelemetryAdapter, TelemetryEvent, telemetry_from_env


class InvestigationService:
    def __init__(self, mcp_client: Any = None, live_mcp_client: Any = None, maps_client: Any = None, model: InvestigationModel | None = None, route_service: RouteExecutor | None = None, policy: GuardrailPolicy | None = None, telemetry: TelemetryAdapter | None = None) -> None:
        self.mcp_client = mcp_client or CityDataMcpClient()
        self.live_mcp_client = live_mcp_client or CityLiveMcpClient()
        self.maps_client = maps_client or GoogleMapsGroundingClient()
        self.model = model or GeminiInvestigationModel()
        self.route_service = route_service or GoogleRoutesService()
        self.policy = policy or GuardrailPolicy()
        self.telemetry = telemetry or telemetry_from_env()

    def record(self, iid: str, trace: list[TraceEvent], *, kind: str, label: str, status: str, tool: str | None = None, provider: str | None = None, policy: PolicyDecision | None = None, count: int | None = None, ms: int | None = None, call: int | None = None, limit: int | None = None) -> None:
        code = policy.code.value if policy else None
        trace.append(TraceEvent(kind=kind, label=label, status=status, tool=tool, result_count=count, latency_ms=ms, policy_code=code, call_number=call, budget_limit=limit))
        self.telemetry.emit(TelemetryEvent(investigation_id=iid, event_type=kind, provider=provider, tool=tool, status=status, policy_code=code, duration_ms=ms, result_count=count, call_number=call, budget_limit=limit))

    def finish(self, result: InvestigationResult) -> InvestigationResult:
        safety = self.policy.validate_public_result(result)
        if safety.outcome != PolicyOutcome.ALLOW:
            result = InvestigationResult(investigation_id=result.investigation_id, status="failed", answer="The investigation result could not be returned safely.", limitations=["Provider details were removed by the response safety policy."])
        self.telemetry.emit(TelemetryEvent(investigation_id=result.investigation_id, event_type="final_result", status=result.status, policy_code=safety.code.value))
        return result

    async def investigate(self, request: InvestigationRequest) -> InvestigationResult:
        iid, trace, budget = str(uuid.uuid4()), [], ExecutionBudget()
        gate = self.policy.check_request(request)
        if gate.outcome != PolicyOutcome.ALLOW:
            self.record(iid, trace, kind="planning", label="Rejected request at the deterministic policy boundary", status="rejected", policy=gate)
            return self.finish(InvestigationResult(investigation_id=iid, status="unsupported", answer=gate.message, limitations=["No model or provider call was made."], trace=trace))
        if request.city == "paris":
            return await self._paris_live(iid, trace)
        self.record(iid, trace, kind="planning", label="Classify question and select a City Data MCP tool", status="completed", policy=gate)
        context, tool_results = json.dumps({"city": request.city, "context": request.context.model_dump(mode="json")}), []
        envelope = final = None
        places, external, map_results, analysis = [], [], {}, []
        while self.policy.check_model_round(budget).outcome == PolicyOutcome.ALLOW:
            started = time.perf_counter()
            try:
                decision = await self.model.decide(request.question, context, tool_results)
            except Exception:
                failure = self.policy.provider_error("Gemini")
                self.record(iid, trace, kind="planning", label="Model decision unavailable", status="failed", provider="gemini", policy=failure, ms=round((time.perf_counter()-started)*1000), call=budget.model_rounds, limit=self.policy.max_model_rounds)
                return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="The investigation could not be planned.", limitations=[failure.message], trace=trace))
            self.telemetry.emit(TelemetryEvent(investigation_id=iid, event_type="planning", provider="gemini", status="completed", policy_code="allowed", duration_ms=round((time.perf_counter()-started)*1000), call_number=budget.model_rounds, budget_limit=self.policy.max_model_rounds))
            final = decision
            gate = self.policy.check_model_decision(decision)
            if gate.outcome != PolicyOutcome.ALLOW:
                self.record(iid, trace, kind="tool_call", label="Rejected model decision", status="rejected", tool=decision.tool, policy=gate)
                return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="The requested operation was rejected.", limitations=[gate.message], trace=trace))
            requested_city = decision.arguments.get("city")
            if requested_city is not None and requested_city != request.city:
                gate = PolicyDecision(outcome="reject", code=PolicyCode.UNSUPPORTED_CITY, message="Tool calls must stay within the selected city.")
                self.record(iid, trace, kind="tool_call", label="Rejected cross-city tool request", status="rejected", tool=decision.tool, policy=gate)
                return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="The requested operation was rejected.", limitations=[gate.message], trace=trace))
            if decision.kind == "unsupported":
                return self.finish(InvestigationResult(investigation_id=iid, status="unsupported", answer=decision.answer or "This question is unsupported.", limitations=["No unsupported tool was executed."], trace=trace))
            if decision.kind == "answer": break
            if decision.tool == "route.intent": return await self._route(iid, request.city, decision, trace, budget)
            if decision.tool == "maps.search_places":
                try:
                    plan = normalize_amenity_plan(request.question, AmenitySearchPlan.model_validate(decision.arguments))
                except Exception:
                    gate = PolicyDecision(outcome="reject", code=PolicyCode.UNTRUSTED_H3, message="The Maps enrichment plan was invalid.")
                    self.record(iid, trace, kind="tool_call", label="Rejected invalid Maps enrichment plan", status="rejected", tool="maps.search_places", policy=gate)
                    return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="The place search plan was invalid.", limitations=[gate.message], trace=trace))
                trusted = set(request.context.selected_h3_cells) | ({x.h3_cell for x in envelope.map_layers} if envelope else set())
                gate = self.policy.check_maps_plan(plan, trusted, budget)
                if gate.outcome != PolicyOutcome.ALLOW:
                    self.record(iid, trace, kind="tool_call", label="Rejected Maps enrichment", status="rejected", tool="maps.search_places", policy=gate)
                    return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="The place search was rejected.", limitations=[gate.message], trace=trace))
                async def search(cell: str, category: str):
                    began = time.perf_counter(); result = await self.maps_client.search_places(category, cell, request.city)
                    return cell, category, result, round((time.perf_counter()-began)*1000)
                try:
                    found = await asyncio.gather(*(search(c, a) for c in plan.h3_cells for a in plan.categories))
                except Exception:
                    failure = self.policy.provider_error("Google Maps Grounding Lite", partial=bool(envelope))
                    self.record(iid, trace, kind="tool_call", label="Google Maps enrichment unavailable", status="failed", provider="google_maps", tool="maps.search_places", policy=failure)
                    return self.finish(InvestigationResult(investigation_id=iid, status="partial", answer="Historical analysis is available, but current Maps context is unavailable.", dataset=envelope.dataset if envelope else None, evidence=envelope.evidence if envelope else [], map_layers=envelope.map_layers if envelope else [], limitations=[failure.message], trace=trace))
                first = budget.maps_calls-len(found)+1
                for offset, (cell, category, result, ms) in enumerate(found):
                    map_results[(cell, category)] = result; places.extend(result.places)
                    external.append({"source":"google_maps","metric":"place_count","value":len(result.places),"unit":"places","source_aggregate":"maps.search_places","filters_applied":{"category":category},"h3_cells":[cell]})
                    self.record(iid, trace, kind="tool_call", label="Called Google Maps Grounding MCP: search_places", status="completed", provider="google_maps", tool="maps.search_places", policy=gate, count=len(result.places), ms=ms, call=first+offset, limit=self.policy.max_maps_calls)
                activity = {x.h3_cell: float(x.value) for x in (envelope.map_layers if envelope else [])}
                analysis = deterministic_amenity_analysis(plan.h3_cells, plan.categories, activity, map_results)
                tool_results.append({"source":"google_maps","places":[x.model_dump(mode="json") for x in places],"amenity_analysis":analysis})
            else:
                gate = self.policy.check_city_data_call(budget)
                if gate.outcome != PolicyOutcome.ALLOW: break
                started = time.perf_counter()
                try:
                    raw = await self.mcp_client.call(decision.tool, decision.arguments)
                    if decision.tool == "describe_dataset":
                        dataset = DatasetMetadata.model_validate(raw); envelope = ToolEnvelope(dataset=dataset, results=[], evidence=[], map_layers=[], limitations=dataset.limitations)
                    else: envelope = ToolEnvelope.model_validate(raw)
                except Exception:
                    failure = self.policy.provider_error("City Data MCP")
                    self.record(iid, trace, kind="tool_call", label="City Data MCP unavailable", status="failed", provider="city_data", tool=f"city_data.{decision.tool}", policy=failure)
                    return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="City Data could not answer this investigation.", limitations=[failure.message], trace=trace))
                tool_results.append({"source":"city_data", **envelope.model_dump(mode="json")})
                self.record(iid, trace, kind="tool_call", label=f"Called City Data MCP: {decision.tool}", status="completed", provider="city_data", tool=f"city_data.{decision.tool}", policy=gate, count=len(envelope.results), ms=round((time.perf_counter()-started)*1000), call=budget.city_data_calls, limit=self.policy.max_city_data_calls)
            context = json.dumps({"request":request.context.model_dump(mode="json"),"available_evidence":tool_results}, default=str)
        if not envelope and not places:
            return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="The investigation did not produce a grounded result.", limitations=["A grounded result is required."], trace=trace))
        if not final or final.kind != "answer":
            gate = PolicyDecision(outcome="fail", code=PolicyCode.TOOL_ROUND_LIMIT, message="The bounded model/tool round limit was reached.")
            self.record(iid, trace, kind="planning", label="Stopped at the bounded model/tool round limit", status="rejected", policy=gate, limit=self.policy.max_model_rounds)
            return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="The investigation exceeded its bounded tool-call budget.", limitations=[gate.message], trace=trace))
        self.record(iid, trace, kind="synthesis", label="Synthesize an evidence-grounded answer", status="completed", policy=self.policy.allow())
        evidence = (envelope.evidence if envelope else []) + [Evidence.model_validate(x) for x in external]
        limitations = list(dict.fromkeys((envelope.limitations if envelope else []) + (["Google Maps place counts are current search context, not an exhaustive census."] if external else [])))
        return self.finish(InvestigationResult(investigation_id=iid, status="answered", answer=final.answer or "No answer was returned.", dataset=envelope.dataset if envelope else None, evidence=evidence, places=places, amenity_analysis=analysis, map_layers=envelope.map_layers if envelope else [], limitations=limitations, trace=trace, follow_up_suggestions=final.follow_up_suggestions))

    async def _paris_live(self, iid: str, trace: list[TraceEvent]) -> InvestigationResult:
        started = time.perf_counter()
        try:
            status = await self.live_mcp_client.get_paris_status()
        except Exception:
            failure = self.policy.provider_error("Paris live network")
            self.record(iid, trace, kind="tool_call", label="Paris live network unavailable", status="failed", provider="city_data", tool="city_live_data.get_live_station_status", policy=failure)
            return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="Paris live network data is unavailable.", limitations=[failure.message], trace=trace))
        stations = status.get("stations", [])
        self.record(iid, trace, kind="tool_call", label="Called City Live Data MCP: get_live_station_status", status="completed", provider="city_data", tool="city_live_data.get_live_station_status", policy=self.policy.allow(), count=len(stations), ms=round((time.perf_counter()-started)*1000))
        return self.finish(InvestigationResult(investigation_id=iid, status="answered", answer=f"Paris live network status returned {len(stations)} stations. This is current operational availability, not historical trip demand.", city_insights=[status], limitations=status.get("limitations", []), trace=trace))

    async def _route(self, iid: str, city: str, decision: ToolDecision, trace: list[TraceEvent], budget: ExecutionBudget) -> InvestigationResult:
        gate = self.policy.reserve_route_resolution(budget)
        if gate.outcome != PolicyOutcome.ALLOW: return self.finish(InvestigationResult(investigation_id=iid,status="failed",answer="Route resolution was rejected.",limitations=[gate.message],trace=trace))
        started=time.perf_counter()
        try: resolved=await asyncio.gather(self.maps_client.resolve_location(decision.arguments["origin"], city),self.maps_client.resolve_location(decision.arguments["destination"], city))
        except Exception:
            failure=self.policy.provider_error("Google Maps Grounding Lite"); self.record(iid,trace,kind="tool_call",label="Google Maps location resolution unavailable",status="failed",provider="google_maps",tool="maps.search_places",policy=failure)
            return self.finish(InvestigationResult(investigation_id=iid,status="failed",answer="The route endpoints could not be resolved.",limitations=[failure.message],trace=trace))
        self.record(iid,trace,kind="tool_call",label="Resolved route endpoints with Google Maps Grounding MCP: search_places",status="completed",provider="google_maps",tool="maps.search_places",policy=gate,count=2,ms=round((time.perf_counter()-started)*1000),call=budget.maps_calls,limit=self.policy.max_maps_calls)
        origin,destination=(x.as_location() for x in resolved); location_gate = self.policy.check_route_locations(city, [origin, destination])
        if location_gate.outcome != PolicyOutcome.ALLOW:
            self.record(iid,trace,kind="tool_call",label="Rejected route endpoints outside selected city",status="rejected",provider="google_maps",tool="maps.search_places",policy=location_gate)
            return self.finish(InvestigationResult(investigation_id=iid,status="failed",answer="The route endpoints are outside the selected city.",limitations=[location_gate.message],trace=trace))
        city_gate=self.policy.check_city_data_call(budget)
        if city_gate.outcome != PolicyOutcome.ALLOW:
            self.record(iid,trace,kind="tool_call",label="Rejected City Data route geography call",status="rejected",provider="city_data",tool="city_data.find_hotspots",policy=city_gate)
            return self.finish(InvestigationResult(investigation_id=iid,status="failed",answer="Historical route geography was rejected.",limitations=[city_gate.message],trace=trace))
        try: envelope=ToolEnvelope.model_validate(await self.mcp_client.call("find_hotspots",{"city":city,"metric":"total_activity","limit":10,"time_filter":{}}))
        except Exception:
            failure=self.policy.provider_error("City Data MCP")
            self.record(iid,trace,kind="tool_call",label="City Data route geography unavailable",status="failed",provider="city_data",tool="city_data.find_hotspots",policy=failure,call=budget.city_data_calls,limit=self.policy.max_city_data_calls)
            return self.finish(InvestigationResult(investigation_id=iid,status="failed",answer="Historical route geography is unavailable.",limitations=[failure.message],trace=trace))
        self.record(iid,trace,kind="tool_call",label="Called City Data MCP: find_hotspots for route geography",status="completed",provider="city_data",tool="city_data.find_hotspots",policy=city_gate,count=len(envelope.results),call=budget.city_data_calls,limit=self.policy.max_city_data_calls)
        waypoints=select_waypoints(origin,destination,envelope.results); gate=self.policy.check_waypoints(waypoints)
        if gate.outcome != PolicyOutcome.ALLOW: return self.finish(InvestigationResult(investigation_id=iid,status="failed",answer="Route waypoints were rejected.",limitations=[gate.message],trace=trace))
        route: RouteDetails|None=None; fallback=False
        for attempt,points in enumerate((waypoints,[]),1):
            if attempt==2 and not waypoints: break
            route_gate=self.policy.reserve_route_call(budget)
            if route_gate.outcome != PolicyOutcome.ALLOW: break
            try:
                route=await self.route_service.compute_bicycle_route(origin,destination,points)
                self.record(iid,trace,kind="tool_call",label="Called Google Routes API: deterministic bicycle route",status="completed",provider="google_routes",tool="routes.compute_bicycle_route",policy=route_gate,count=1,call=budget.routes_calls,limit=self.policy.max_routes_calls); break
            except Exception:
                fallback=bool(points); self.record(iid,trace,kind="tool_call",label="Google Routes API bicycle route attempt unavailable",status="failed",provider="google_routes",tool="routes.compute_bicycle_route",policy=self.policy.provider_error("Google Routes API",partial=True),call=budget.routes_calls,limit=self.policy.max_routes_calls)
        if not route: return self.finish(InvestigationResult(investigation_id=iid,status="partial",answer="Historical route geography is available, but a bicycle route could not be computed.",dataset=envelope.dataset,evidence=envelope.evidence,map_layers=envelope.map_layers,city_insights=envelope.results,limitations=["Google Routes API did not return a validated bicycle route."],trace=trace))
        limitations=list(dict.fromkeys(envelope.limitations+[route.warning]+(["The route was computed directly after waypoint routing failed."] if fallback and not route.waypoints else [])))
        return self.finish(InvestigationResult(investigation_id=iid,status="answered",answer=f"The validated bicycle route from {origin.name} to {destination.name} is {route.distance_m/1000:.1f} km and about {route.duration_seconds/60:.0f} minutes.",dataset=envelope.dataset,evidence=envelope.evidence,map_layers=envelope.map_layers,city_insights=envelope.results,route=route,limitations=limitations,trace=trace))
