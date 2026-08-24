import logging

from apps.api.app.agent.telemetry import LangSmithTelemetryAdapter, LocalTelemetryAdapter, SafeTelemetryAdapter, TelemetryEvent


def event():
    return TelemetryEvent(investigation_id="id",event_type="tool_call",provider="city_data",tool="find_hotspots",status="completed",policy_code="allowed",result_count=2)


def test_local_telemetry_contains_only_sanitized_schema(caplog):
    with caplog.at_level(logging.INFO,logger="cityscope.telemetry"):
        LocalTelemetryAdapter().emit(event())
    assert "find_hotspots" in caplog.text
    assert "question" not in caplog.text and "headers" not in caplog.text and "prompt" not in caplog.text


def test_export_failure_never_breaks_request():
    class Broken:
        def emit(self,_): raise RuntimeError("secret provider payload")
    SafeTelemetryAdapter(Broken()).emit(event())


def test_langsmith_zero_sample_makes_no_export():
    class Client:
        def create_run(self,**kwargs): raise AssertionError("must not export")
    LangSmithTelemetryAdapter(api_key="unused",sample_rate=0.0,client=Client()).emit(event())
