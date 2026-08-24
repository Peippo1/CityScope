from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from apps.api.app.agent.places import MapsSearchResult
from apps.api.app.agent.route_service import ResolvedPlace, RouteDetails
from apps.api.app.agent.schemas import InvestigationRequest, ToolDecision
from apps.api.app.agent.service import InvestigationService
from apps.api.app.agent.telemetry import OffTelemetryAdapter
from services.city_data_mcp.schemas import DatasetMetadata, Evidence, MapLayer, ToolEnvelope

CELL = "892a100d2d7ffff"


def fixture() -> dict[str, Any]:
    dataset = DatasetMetadata(city="london",dataset_id="eval",dataset_name="TfL London Cycling",snapshot_id="may-2026",observation_start="2026-05-01",observation_end="2026-05-31",source_organisation="TfL",mode="cycling",h3_resolution=9,historical=True,available_metrics=["starts"],supported_temporal_filters=[],limitations=["Historical May 2026 snapshot."],provenance_summary={})
    return ToolEnvelope(dataset=dataset,results=[{"h3_cell":CELL,"value":7,"rank":1}],evidence=[Evidence(metric="starts",value=7,unit="journeys",source_aggregate="activity",h3_cells=[CELL],filters_applied={})],map_layers=[MapLayer(h3_cell=CELL,metric="starts",value=7,rank=1)],limitations=dataset.limitations).model_dump(mode="json")


class FakeModel:
    def __init__(self, decisions): self.decisions=iter(decisions); self.calls=0
    async def decide(self,*_): self.calls+=1; return next(self.decisions)


class FakeCity:
    def __init__(self,failure=False,secret=False): self.calls=[]; self.failure=failure; self.secret=secret
    async def call(self,tool,args):
        self.calls.append((tool,args))
        if self.failure: raise RuntimeError("credential=TEST_SENTINEL_DO_NOT_EXPOSE" if self.secret else "provider details")
        return fixture()["dataset"] if tool=="describe_dataset" else fixture()


class FakeMaps:
    def __init__(self,failure=False): self.calls=[]; self.failure=failure
    async def search_places(self,category,cell):
        self.calls.append((category,cell))
        if self.failure: raise RuntimeError("provider details")
        return MapsSearchResult.model_validate({"places":[{"place_id":"ChIJeval","name":"Cafe","latitude":51.5,"longitude":-0.1,"maps_uri":"https://maps.google.com/eval","category":category,"h3_cell":cell}]})
    async def resolve_location(self,name):
        self.calls.append(("resolve",name)); return ResolvedPlace(name=name,place_id=f"place-{len(self.calls)}",latitude=51.50+len(self.calls)/100,longitude=-0.1,maps_uri="https://maps.google.com/eval")


class FakeRoutes:
    def __init__(self,failure=False): self.calls=[]; self.failure=failure
    async def compute_bicycle_route(self,origin,destination,waypoints):
        self.calls.append((origin,destination,waypoints))
        if self.failure: raise RuntimeError("malformed route")
        return RouteDetails(distance_m=2000,duration_seconds=800,polyline="encoded",origin=origin,destination=destination,waypoints=waypoints)


def decisions(scenario):
    hot=ToolDecision(kind="call_tool",tool="find_hotspots",arguments={"city":"london","metric":"starts","limit":3,"time_filter":{}})
    maps=ToolDecision(kind="call_tool",tool="maps.search_places",arguments={"h3_cells":[CELL],"categories":["cafe"]})
    answer=ToolDecision(kind="answer",answer="Grounded answer.")
    if scenario=="dataset": return [ToolDecision(kind="call_tool",tool="describe_dataset",arguments={"city":"london"}),answer]
    if scenario in {"historical"}: return [hot,answer]
    if scenario in {"amenity","maps_failure"}: return [hot,maps,answer]
    if scenario=="maps_first": return [maps]
    if scenario=="untrusted_h3": return [ToolDecision(kind="call_tool",tool="maps.search_places",arguments={"h3_cells":["892a100d2d3ffff"],"categories":["cafe"]})]
    if scenario in {"route","route_failure"}: return [ToolDecision(kind="call_tool",tool="route.intent",arguments={"origin":"King's Cross","destination":"Borough"})]
    if scenario=="route_coordinates": return [ToolDecision(kind="call_tool",tool="route.intent",arguments={"origin":"A","destination":"B","latitude":51.5})]
    if scenario=="round_limit": return [hot,hot,hot]
    if scenario in {"city_failure","secret_failure"}: return [hot]
    return []


async def evaluate(case):
    scenario=case["scenario"]; model=FakeModel(decisions(scenario)); city=FakeCity(scenario in {"city_failure","secret_failure"},scenario=="secret_failure"); maps=FakeMaps(scenario=="maps_failure"); routes=FakeRoutes(scenario=="route_failure")
    context={"selected_h3_cells":[CELL]} if scenario=="untrusted_h3" else {}
    result=await InvestigationService(mcp_client=city,maps_client=maps,model=model,route_service=routes,telemetry=OffTelemetryAdapter()).investigate(InvestigationRequest(question=case["question"],context=context))
    sequence=[x.tool for x in result.trace if x.kind=="tool_call" and x.tool]
    sources={x.source for x in result.evidence}; codes={x.policy_code for x in result.trace if x.policy_code}
    calls={"gemini":model.calls,"city_data":len(city.calls),"google_maps":len(maps.calls),"google_routes":len(routes.calls)}
    errors=[]
    if result.status!=case["expected_status"]: errors.append(f"status {result.status}")
    if sequence!=case["expected_tool_sequence"]: errors.append(f"tools {sequence}")
    if not set(case["required_evidence_sources"]).issubset(sources): errors.append(f"evidence {sorted(sources)}")
    if not set(case["required_policy_codes"]).issubset(codes): errors.append(f"policy {sorted(codes)}")
    if any(tool in sequence for tool in case["forbidden_tools"]): errors.append("forbidden tool")
    if any(calls[k]>v for k,v in case["maximum_provider_calls"].items()): errors.append(f"calls {calls}")
    if "TEST_SENTINEL_DO_NOT_EXPOSE" in result.model_dump_json(): errors.append("credential exposure")
    return {"case_id":case["case_id"],"passed":not errors,"status":result.status,"tool_sequence":sequence,"provider_calls":calls,"errors":errors}


def run(path: Path):
    dataset=json.loads(path.read_text()); results=[asyncio.run(evaluate(x)) for x in dataset["cases"]]
    return {"version":dataset["version"],"passed":all(x["passed"] for x in results),"results":results}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--cases",type=Path,default=Path(__file__).with_name("cases.json")); parser.add_argument("--json-output",type=Path); args=parser.parse_args()
    report=run(args.cases); rendered=json.dumps(report,indent=2)
    if args.json_output: args.json_output.write_text(rendered+"\n")
    print(rendered); print(f"{sum(x['passed'] for x in report['results'])}/{len(report['results'])} deterministic evaluations passed")
    raise SystemExit(0 if report["passed"] else 1)


if __name__=="__main__": main()
