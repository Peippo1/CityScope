from __future__ import annotations

import asyncio
import json
import time
import uuid
import h3
from typing import Any

from services.city_data_mcp.schemas import DatasetMetadata, Evidence, ToolEnvelope
from .. import config
from ..cities import get_city
from ..schemas import CityComparisonResponse

from .mcp_client import CityDataMcpClient
from .live_mcp_client import CityLiveMcpClient
from .model import GeminiInvestigationModel, InvestigationModel
from .adk_runtime import ADKInvestigationModel
from .model import GemmaJourneyCharacterScorer
from .places import AmenitySearchPlan, GoogleMapsGroundingClient, deterministic_amenity_analysis, normalize_amenity_plan
from .policy import ExecutionBudget, GuardrailPolicy, PolicyCode, PolicyDecision, PolicyOutcome
from .route_service import GoogleRoutesService, RouteDetails, RouteExecutor, select_waypoints
from .route_templates import match_route_templates
from .journey_planner import JourneyPlanner
from .schemas import InvestigationRequest, InvestigationResult, TraceEvent, ToolDecision, JourneyPlan, JourneySegment
from .telemetry import TelemetryAdapter, TelemetryEvent, telemetry_from_env


class InvestigationService:
    def __init__(self, mcp_client: Any = None, live_mcp_client: Any = None, maps_client: Any = None, model: InvestigationModel | None = None, route_service: RouteExecutor | None = None, policy: GuardrailPolicy | None = None, telemetry: TelemetryAdapter | None = None, gemma_scorer: GemmaJourneyCharacterScorer | None = None) -> None:
        self.mcp_client = mcp_client or CityDataMcpClient()
        self.live_mcp_client = live_mcp_client or CityLiveMcpClient()
        self.maps_client = maps_client or GoogleMapsGroundingClient()
        self.model = model or ADKInvestigationModel()
        self.adk_runtime = isinstance(self.model, ADKInvestigationModel)
        self.gemma_scorer = gemma_scorer or GemmaJourneyCharacterScorer()
        self.route_service = route_service or GoogleRoutesService()
        self.policy = policy or GuardrailPolicy()
        self.telemetry = telemetry or telemetry_from_env()

    def record(self, iid: str, trace: list[TraceEvent], *, kind: str, label: str, status: str, tool: str | None = None, provider: str | None = None, policy: PolicyDecision | None = None, count: int | None = None, ms: int | None = None, call: int | None = None, limit: int | None = None) -> None:
        code = policy.code.value if policy else None
        trace.append(TraceEvent(kind=kind, label=label, status=status, tool=tool, provider=provider, result_count=count, latency_ms=ms, policy_code=code, call_number=call, budget_limit=limit))
        self.telemetry.emit(TelemetryEvent(investigation_id=iid, event_type=kind, provider=provider, tool=tool, status=status, policy_code=code, duration_ms=ms, result_count=count, call_number=call, budget_limit=limit))

    def finish(self, result: InvestigationResult) -> InvestigationResult:
        safety = self.policy.validate_public_result(result)
        if safety.outcome != PolicyOutcome.ALLOW:
            result = InvestigationResult(investigation_id=result.investigation_id, status="failed", answer="The investigation result could not be returned safely.", limitations=["Provider details were removed by the response safety policy."])
        self.telemetry.emit(TelemetryEvent(investigation_id=result.investigation_id, event_type="final_result", status=result.status, policy_code=safety.code.value))
        return result

    @staticmethod
    def _comparison_unit(metric: str) -> str:
        return {
            "trips_per_active_station_day": "trips/station/day",
            "median_trip_duration_minutes": "minutes",
            "peak_hour_share": "share",
            "weekend_share": "share",
            "hotspot_concentration": "share",
        }[metric]

    @classmethod
    def _comparison_answer(cls, comparison: CityComparisonResponse) -> str:
        labels = {
            "trips_per_active_station_day": "trips per active station per day",
            "median_trip_duration_minutes": "median trip duration",
            "peak_hour_share": "peak-hour share",
            "weekend_share": "weekend share",
            "hotspot_concentration": "hotspot concentration",
        }
        unit = cls._comparison_unit(comparison.metric)

        def value(row) -> str:
            if unit == "share":
                return f"{row.value * 100:.1f}%"
            if unit == "minutes":
                return f"{row.value:.1f} minutes"
            return f"{row.value:.2f} trips/station/day"

        rows = sorted(comparison.cities, key=lambda row: row.rank)
        ranking = ", ".join(f"{row.city_name} ({value(row)})" for row in rows)
        return f"{rows[0].city_name} ranks first for {labels[comparison.metric]} in the matched May 2026 cohort. The normalized ranking is {ranking}."

    @staticmethod
    def _historical_answer(request: InvestigationRequest, envelope: ToolEnvelope | None, analysis: list[dict[str, Any]], fallback: str | None) -> str:
        if analysis:
            row = min(analysis, key=lambda item: (item["scarcity_rank"], -item["mobility_value"], item["h3_cell"]))
            return (
                f"H3 area {row['h3_cell']} has the fewest observed {row['category']} results "
                f"({row['place_count']}) among the investigated high-activity areas, with {row['mobility_value']:.0f} historical journeys. "
                "Place counts are current Google Maps context, not a complete census."
            )
        if envelope and envelope.map_layers:
            rows = sorted(envelope.map_layers, key=lambda item: (item.rank or 9999, -item.value, item.h3_cell))
            top = rows[0]
            metric = top.metric.replace("_", " ")
            return f"In the selected historical snapshot, H3 area {top.h3_cell} is the highest returned area for {metric}, with {top.value:,.0f} journeys."
        if envelope and envelope.dataset:
            return f"{envelope.dataset.dataset_name} is a historical snapshot covering {envelope.dataset.observation_start} to {envelope.dataset.observation_end}."
        return fallback or "No grounded answer was returned."

    async def investigate(self, request: InvestigationRequest) -> InvestigationResult:
        iid, trace, budget = str(uuid.uuid4()), [], ExecutionBudget()
        gate = self.policy.check_request(request)
        if gate.outcome != PolicyOutcome.ALLOW:
            self.record(iid, trace, kind="planning", label="Rejected request at the deterministic policy boundary", status="rejected", policy=gate)
            return self.finish(InvestigationResult(investigation_id=iid, status="unsupported", answer=gate.message, limitations=["No model or provider call was made."], trace=trace))
        if request.city == "paris" and not any(term in request.question.lower() for term in ("route", "cycling", "cycle", "bicycle", "ride", "journey")):
            return await self._paris_live(iid, trace)
        if self.adk_runtime:
            self.record(iid, trace, kind="planning", label="CityScope ADK investigation started", status="completed", provider="gemini", call=1, limit=self.policy.max_model_rounds)
            self.record(iid, trace, kind="planning", label="inspect_city_capabilities", status="completed", provider="city_data")
        self.record(iid, trace, kind="planning", label="Classify question and select a City Data MCP tool", status="completed", policy=gate)
        context, tool_results = json.dumps({"city": request.city, "context": request.context.model_dump(mode="json")}), []
        character_score = None
        if self.gemma_scorer and any(term in request.question.lower() for term in ("scenic", "green", "lively", "cultural", "relaxed", "coffee")):
            started = time.perf_counter()
            try:
                character_score = await asyncio.wait_for(self.gemma_scorer.score(request.question, request.context.evidence_summary or "No additional evidence supplied."), timeout=config.GEMMA_TIMEOUT_SECONDS)
                tool_results.append({"source": "gemma", "journey_character_score": character_score.model_dump(mode="json")})
                self.record(iid, trace, kind="tool_call", label="journey_character.score [Gemma 4]", status="completed", provider="gemini", tool="journey_character.score", ms=round((time.perf_counter()-started)*1000), call=1, limit=1)
            except Exception:
                self.record(iid, trace, kind="tool_call", label="journey_character.score [Gemma 4]", status="failed", provider="gemini", tool="journey_character.score", ms=round((time.perf_counter()-started)*1000), call=1, limit=1)
        envelope = final = None
        places, external, map_results, analysis, city_insights, comparison_evidence, comparison_limitations = [], [], {}, [], [], [], []
        while self.policy.check_model_round(budget).outcome == PolicyOutcome.ALLOW:
            started = time.perf_counter()
            try:
                decision = await asyncio.wait_for(
                    self.model.decide(request.question, context, tool_results),
                    timeout=config.MODEL_TIMEOUT_SECONDS,
                )
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
            if decision.tool != "compare_cities" and requested_city is not None and requested_city != request.city:
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
                    if decision.tool == "compare_cities":
                        comparison = CityComparisonResponse.model_validate(raw)
                        city_insights = [comparison.model_dump(mode="json")]
                        comparison_limitations = comparison.limitations
                        comparison_evidence = [Evidence(metric=comparison.metric, value=row.value, unit=self._comparison_unit(comparison.metric), source_aggregate="cross_city_canonical_trips", filters_applied={"observation_period": comparison.observation_period}, h3_cells=[], category=row.city_name) for row in comparison.cities]
                    elif decision.tool == "describe_dataset":
                        dataset = DatasetMetadata.model_validate(raw); envelope = ToolEnvelope(dataset=dataset, results=[], evidence=[], map_layers=[], limitations=dataset.limitations)
                    else: envelope = ToolEnvelope.model_validate(raw)
                except Exception:
                    failure = self.policy.provider_error("City Data MCP")
                    self.record(iid, trace, kind="tool_call", label="City Data MCP unavailable", status="failed", provider="city_data", tool=f"city_data.{decision.tool}", policy=failure)
                    return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="City Data could not answer this investigation.", limitations=[failure.message], trace=trace))
                tool_results.append({"source":"city_data", **(comparison.model_dump(mode="json") if decision.tool == "compare_cities" else envelope.model_dump(mode="json"))})
                result_count = len(comparison.cities) if decision.tool == "compare_cities" else len(envelope.results)
                self.record(iid, trace, kind="tool_call", label=f"Called City Data MCP: {decision.tool}", status="completed", provider="city_data", tool=f"city_data.{decision.tool}", policy=gate, count=result_count, ms=round((time.perf_counter()-started)*1000), call=budget.city_data_calls, limit=self.policy.max_city_data_calls)
                if decision.tool == "compare_cities":
                    final = ToolDecision(
                        kind="answer",
                        answer=self._comparison_answer(comparison),
                        follow_up_suggestions=[
                            "How does peak-hour share compare across London, New York City, Chicago, and Washington, DC?",
                            "How does weekend share compare across London, New York City, Chicago, and Washington, DC?",
                            "How does median trip duration compare across London, New York City, Chicago, and Washington, DC?",
                        ],
                    )
                    break
            context = json.dumps({"request":request.context.model_dump(mode="json"),"available_evidence":tool_results}, default=str)
        if not envelope and not places and not city_insights:
            return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="The investigation did not produce a grounded result.", limitations=["A grounded result is required."], trace=trace))
        if not final or final.kind != "answer":
            gate = PolicyDecision(outcome="fail", code=PolicyCode.TOOL_ROUND_LIMIT, message="The bounded model/tool round limit was reached.")
            self.record(iid, trace, kind="planning", label="Stopped at the bounded model/tool round limit", status="rejected", policy=gate, limit=self.policy.max_model_rounds)
            return self.finish(InvestigationResult(investigation_id=iid, status="failed", answer="The investigation exceeded its bounded tool-call budget.", limitations=[gate.message], trace=trace))
        self.record(iid, trace, kind="synthesis", label="compose_result", status="completed", policy=self.policy.allow())
        evidence = (envelope.evidence if envelope else []) + comparison_evidence + [Evidence.model_validate(x) for x in external]
        limitations = list(dict.fromkeys((envelope.limitations if envelope else []) + comparison_limitations + (["Google Maps place counts are current search context, not an exhaustive census."] if external else [])))
        answer = self._historical_answer(request, envelope, analysis, final.answer)
        if self.adk_runtime:
            self.record(iid, trace, kind="synthesis", label="Investigation complete", status="completed", provider="gemini", policy=self.policy.allow())
        return self.finish(InvestigationResult(investigation_id=iid, status="answered", answer=answer, dataset=envelope.dataset if envelope else None, evidence=evidence, places=places, amenity_analysis=analysis, city_insights=city_insights, map_layers=envelope.map_layers if envelope else [], limitations=limitations, trace=trace, follow_up_suggestions=final.follow_up_suggestions, journey_character_score=character_score.model_dump(mode="json") if character_score else None))

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
        if self.adk_runtime:
            self.record(iid, trace, kind="planning", label="route.intent", status="completed", provider="gemini", tool="route.intent", call=budget.model_rounds, limit=self.policy.max_model_rounds)
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
        city_gate = self.policy.allow()
        if not get_city(city).historical:
            envelope = ToolEnvelope(
                dataset=DatasetMetadata(city=city, dataset_id="route-only", dataset_name=f"{get_city(city).name} route planning", snapshot_id="route-only", observation_start="", observation_end="", source_organisation="CityScope", mode="bicycle routing", h3_resolution=0, historical=False, available_metrics=[], supported_temporal_filters=[], limitations=[f"No historical CityScope mobility dataset is available for {get_city(city).name}; route suggestions use named places and Google Maps/Routes."], provenance_summary={}),
                results=[], evidence=[], map_layers=[], limitations=[f"No historical CityScope mobility dataset is available for {get_city(city).name}; route suggestions use named places and Google Maps/Routes."],
            )
            waypoints = []
        else:
            city_gate=self.policy.check_city_data_call(budget)
        if get_city(city).historical and city_gate.outcome != PolicyOutcome.ALLOW:
            self.record(iid,trace,kind="tool_call",label="Rejected City Data route geography call",status="rejected",provider="city_data",tool="city_data.find_hotspots",policy=city_gate)
            return self.finish(InvestigationResult(investigation_id=iid,status="failed",answer="Historical route geography was rejected.",limitations=[city_gate.message],trace=trace))
        try:
            if get_city(city).historical:
                envelope=ToolEnvelope.model_validate(await self.mcp_client.call("find_hotspots",{"city":city,"metric":"total_activity","limit":10,"time_filter":{}}))
        except Exception:
            failure=self.policy.provider_error("City Data MCP")
            self.record(iid,trace,kind="tool_call",label="City Data route geography unavailable",status="failed",provider="city_data",tool="city_data.find_hotspots",policy=failure,call=budget.city_data_calls,limit=self.policy.max_city_data_calls)
            return self.finish(InvestigationResult(investigation_id=iid,status="failed",answer="Historical route geography is unavailable.",limitations=[failure.message],trace=trace))
        if get_city(city).historical:
            self.record(iid,trace,kind="tool_call",label="Called City Data MCP: find_hotspots for route geography",status="completed",provider="city_data",tool="city_data.find_hotspots",policy=city_gate,count=len(envelope.results),call=budget.city_data_calls,limit=self.policy.max_city_data_calls)
            waypoints=select_waypoints(origin,destination,envelope.results)
        gate=self.policy.check_waypoints(waypoints)
        if gate.outcome != PolicyOutcome.ALLOW: return self.finish(InvestigationResult(investigation_id=iid,status="failed",answer="Route waypoints were rejected.",limitations=[gate.message],trace=trace))
        if self.adk_runtime and get_city(city).historical:
            self.record(iid, trace, kind="planning", label="deterministic waypoint selection", status="completed", provider="city_data", tool="city_data.find_hotspots", call=budget.city_data_calls, limit=self.policy.max_city_data_calls)
        return_to_origin = bool(decision.arguments.get("return_to_origin"))
        planner = JourneyPlanner(self.route_service, lambda: self.policy.reserve_route_call(budget).outcome == PolicyOutcome.ALLOW)
        planned = await planner.plan(origin, destination, waypoints, return_to_origin)
        if not planned:
            self.record(iid,trace,kind="tool_call",label="Google Routes API bicycle route unavailable",status="failed",provider="google_routes",tool="routes.compute_bicycle_route",policy=self.policy.provider_error("Google Routes API", partial=True),call=budget.routes_calls,limit=self.policy.max_routes_calls)
            return self.finish(InvestigationResult(investigation_id=iid,status="partial",answer="Historical route geography is available, but a bicycle route could not be computed.",dataset=envelope.dataset,evidence=envelope.evidence,map_layers=envelope.map_layers,city_insights=envelope.results,limitations=["Google Routes API did not return a validated bicycle route."],trace=trace))
        route, fallback = planned.outbound, planned.used_direct_fallback
        route_gate = self.policy.allow()
        self.record(iid,trace,kind="tool_call",label="Called Google Routes API: deterministic bicycle route",status="completed",provider="google_routes",tool="routes.compute_bicycle_route",policy=route_gate,count=1,call=budget.routes_calls,limit=self.policy.max_routes_calls)
        templates = match_route_templates(
            origin.name,
            destination.name,
            decision.arguments.get("preferences"),
            decision.arguments.get("requested_stops"),
            city=city,
        )
        requested_template_id = decision.arguments.get("template_id")
        if requested_template_id:
            templates = [template for template in templates if template.template_id == requested_template_id]
        template = templates[0] if templates else None
        if template:
            self.record(iid, trace, kind="planning", label=f"Matched curated route template: {template.name}", status="completed", provider="city_data", tool="route.template")
        segments = [JourneySegment(label="Outbound", purpose="Start to destination", route=route)]
        limitations = list(dict.fromkeys(envelope.limitations + [route.warning] + (["The route was computed directly after waypoint routing failed."] if fallback and not route.waypoints else [])))
        if planned.return_route:
            segments.append(JourneySegment(label="Return loop", purpose="Destination back to start", route=planned.return_route))
            self.record(iid, trace, kind="tool_call", label="Called Google Routes API: return bicycle route", status="completed", provider="google_routes", tool="routes.compute_bicycle_route", policy=route_gate, count=1, call=budget.routes_calls, limit=self.policy.max_routes_calls)
        elif return_to_origin:
            limitations.append("A return route could not be computed; the outbound route is still available.")
        requested_stops = list(dict.fromkeys(decision.arguments.get("requested_stops") or []))
        if "interesting" in (decision.arguments.get("preferences") or []) and "point_of_interest" not in requested_stops:
            requested_stops.append("point_of_interest")
        requested_stops = requested_stops[:2]
        selected_stops = []
        if requested_stops:
            trusted_cells = [item.h3_cell for item in envelope.map_layers[:3]]
            if not trusted_cells and not get_city(city).historical:
                trusted_cells = [h3.latlng_to_cell(origin.latitude, origin.longitude, 9), h3.latlng_to_cell(destination.latitude, destination.longitude, 9)]
            if trusted_cells:
                try:
                    plan = AmenitySearchPlan(h3_cells=trusted_cells, categories=requested_stops)
                    maps_gate = self.policy.check_maps_plan(plan, trusted_cells, budget)
                    if maps_gate.outcome == PolicyOutcome.ALLOW:
                        async def search(cell: str, category: str):
                            return await self.maps_client.search_places(category, cell, city)
                        found = await asyncio.gather(*(search(cell, category) for cell in plan.h3_cells for category in plan.categories))
                        for result in found:
                            selected_stops.extend(result.places)
                        self.record(iid, trace, kind="tool_call", label="Called Google Maps Grounding MCP: journey amenity search", status="completed", provider="google_maps", tool="maps.search_places", policy=maps_gate, count=len(selected_stops), call=budget.maps_calls, limit=self.policy.max_maps_calls)
                        if selected_stops:
                            evidence = list(envelope.evidence) + [Evidence(metric="journey_place_count", value=len(selected_stops), unit="places", source_aggregate="maps.search_places", filters_applied={"categories": plan.categories}, h3_cells=plan.h3_cells)]
                        else:
                            evidence = envelope.evidence
                    else:
                        evidence = envelope.evidence
                except Exception:
                    evidence = envelope.evidence
                    limitations.append("Google Maps place suggestions were unavailable; verify stops locally.")
            else:
                evidence = envelope.evidence
        else:
            evidence = envelope.evidence
        provenance = ["Google Maps Grounding for named places", "Google Routes API for bicycle routing", "City Data MCP historical evidence"]
        if template:
            provenance.append(f"Curated route example: {template.name} ({template.source_url})")
        journey = JourneyPlan(
            summary=f"{origin.name} to {destination.name}" + (" and back" if return_to_origin else ""),
            segments=segments,
            selected_stops=selected_stops,
            warnings=limitations,
            provenance=provenance,
            template_id=template.template_id if template else None,
            template_name=template.name if template else None,
            template_description=template.description if template else None,
            template_tags=list(template.tags) if template else [],
            template_source_url=template.source_url if template else None,
            template_notice="Curated route example, not live popularity data; Google Routes supplies the final geometry." if template else None,
            template_waypoint_hints=list(template.waypoint_hints) if template else [],
        )
        if self.adk_runtime:
            self.record(iid,trace,kind="synthesis",label="validate_route",status="completed",provider="google_routes",tool="routes.compute_bicycle_route",call=budget.routes_calls,limit=self.policy.max_routes_calls)
            self.record(iid,trace,kind="synthesis",label="compose_result",status="completed",policy=self.policy.allow())
            self.record(iid,trace,kind="synthesis",label="Investigation complete",status="completed",provider="gemini",policy=self.policy.allow())
        return self.finish(InvestigationResult(investigation_id=iid,status="answered",answer=f"The validated bicycle journey from {origin.name} to {destination.name}" + (" and back" if return_to_origin else "") + f" is {route.distance_m/1000:.1f} km outbound and about {route.duration_seconds/60:.0f} minutes.",dataset=envelope.dataset,evidence=evidence,map_layers=envelope.map_layers,city_insights=envelope.results,route=route,journey_plan=journey,places=selected_stops,limitations=limitations,trace=trace))
