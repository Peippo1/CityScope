import json

from apps.api.app.agent.telemetry import LocalTelemetryAdapter, SafeTelemetryAdapter, TelemetryEvent
from apps.api.app.observability import new_request_id, set_request_context, reset_request_context
import apps.api.app.observability as observability


def test_request_ids_are_bounded_and_invalid_values_are_replaced():
    assert new_request_id("release-123") == "release-123"
    generated = new_request_id("prompt with spaces")
    assert generated != "prompt with spaces"
    assert len(generated) <= 64


def test_local_telemetry_contains_metadata_only(capsys):
    tokens = set_request_context("release-123", "cycling")
    try:
        LocalTelemetryAdapter().emit(TelemetryEvent(
            investigation_id="investigation-123",
            event_type="tool_call",
            provider="google_routes",
            status="completed",
            duration_ms=42,
        ))
    finally:
        reset_request_context(tokens)

    payload = json.loads(capsys.readouterr().out)
    assert payload["request_id"] == "release-123"
    assert payload["activity"] == "cycling"
    assert payload["event"] == "investigation.telemetry"
    assert "prompt" not in payload
    assert "coordinates" not in payload


def test_telemetry_failure_is_non_fatal():
    class BrokenAdapter:
        def emit(self, event):
            raise RuntimeError("telemetry unavailable")

    SafeTelemetryAdapter(BrokenAdapter()).emit(TelemetryEvent(
        investigation_id="investigation-123", event_type="final_result", status="answered"
    ))


def test_observability_export_failure_is_non_fatal(monkeypatch):
    class BrokenStream:
        def write(self, _: str) -> int:
            raise OSError("stream unavailable")

        def flush(self) -> None:
            raise OSError("stream unavailable")

    monkeypatch.setattr(observability.sys, "stdout", BrokenStream())
    observability.emit_event("request.completed", status_code=200)
