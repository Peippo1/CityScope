import json

from apps.api.app.agent.telemetry import LangSmithTelemetryAdapter, LocalTelemetryAdapter, SafeTelemetryAdapter, TelemetryEvent


def event():
    return TelemetryEvent(investigation_id="id",event_type="tool_call",provider="city_data",tool="find_hotspots",status="completed",policy_code="allowed",result_count=2)


def test_local_telemetry_contains_only_sanitized_schema(capsys):
    LocalTelemetryAdapter().emit(event())
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "find_hotspots"
    assert "question" not in payload and "headers" not in payload and "prompt" not in payload


def test_provider_diagnostic_telemetry_contains_category_not_exception_details(capsys):
    LocalTelemetryAdapter().emit(TelemetryEvent(
        investigation_id="id",
        event_type="tool_call",
        provider="google_maps",
        tool="maps.search_places",
        status="failed",
        error_category="transport",
        operation="maps.search_places",
        duration_ms=1250,
        upstream_response_received=False,
    ))
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_category"] == "transport"
    assert payload["operation"] == "maps.search_places"
    assert payload["upstream_response_received"] is False
    assert "secret" not in json.dumps(payload)


def test_export_failure_never_breaks_request():
    class Broken:
        def emit(self,_): raise RuntimeError("secret provider payload")
    SafeTelemetryAdapter(Broken()).emit(event())


def test_langsmith_zero_sample_makes_no_export():
    class Client:
        def create_run(self,**kwargs): raise AssertionError("must not export")
    LangSmithTelemetryAdapter(api_key="unused",sample_rate=0.0,client=Client()).emit(event())
