from __future__ import annotations

import json
import logging
import os
import random
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


LOGGER = logging.getLogger("cityscope.telemetry")


class TelemetryEvent(BaseModel):
    investigation_id: str
    event_type: Literal["planning", "tool_call", "synthesis", "final_result"]
    provider: Literal["gemini", "city_data", "google_maps", "google_routes"] | None = None
    tool: str | None = None
    status: Literal["completed", "rejected", "failed", "answered", "partial", "unsupported"]
    policy_code: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    result_count: int | None = Field(default=None, ge=0)
    call_number: int | None = Field(default=None, ge=1)
    budget_limit: int | None = Field(default=None, ge=1)


class TelemetryAdapter(Protocol):
    def emit(self, event: TelemetryEvent) -> None: ...


class OffTelemetryAdapter:
    def emit(self, event: TelemetryEvent) -> None:
        return None


class LocalTelemetryAdapter:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or LOGGER

    def emit(self, event: TelemetryEvent) -> None:
        self.logger.info(json.dumps(event.model_dump(mode="json", exclude_none=True), sort_keys=True))


class SafeTelemetryAdapter:
    """Telemetry must never affect investigation availability."""

    def __init__(self, inner: TelemetryAdapter) -> None:
        self.inner = inner

    def emit(self, event: TelemetryEvent) -> None:
        try:
            self.inner.emit(event)
        except Exception:
            LOGGER.warning("Telemetry export failed", exc_info=False)


class LangSmithTelemetryAdapter:
    """Optional metadata-only exporter. No prompts or provider payloads enter this API."""

    def __init__(self, *, api_key: str, project: str = "cityscope", sample_rate: float = 0.0, client: Any | None = None) -> None:
        self.project = project
        self.sample_rate = min(1.0, max(0.0, sample_rate))
        if client is None:
            try:
                from langsmith import Client
            except ImportError as exc:
                raise RuntimeError("LangSmith telemetry requires the optional observability dependency") from exc
            client = Client(api_key=api_key)
        self.client = client

    def emit(self, event: TelemetryEvent) -> None:
        if self.sample_rate <= 0 or random.random() >= self.sample_rate:
            return
        now = datetime.now(timezone.utc)
        metadata = event.model_dump(mode="json", exclude_none=True)
        self.client.create_run(
            name=f"cityscope.{event.event_type}",
            run_type="tool",
            inputs={"metadata": metadata},
            outputs={"status": event.status},
            start_time=now,
            end_time=now,
            project_name=self.project,
        )


def telemetry_from_env() -> SafeTelemetryAdapter:
    mode = os.getenv("CITYSCOPE_TELEMETRY", "local").strip().lower()
    if mode == "off":
        return SafeTelemetryAdapter(OffTelemetryAdapter())
    if mode == "langsmith":
        api_key = os.getenv("LANGSMITH_API_KEY", "")
        if not api_key:
            LOGGER.warning("LangSmith telemetry requested but LANGSMITH_API_KEY is missing; telemetry is off")
            return SafeTelemetryAdapter(OffTelemetryAdapter())
        try:
            sample_rate = float(os.getenv("LANGSMITH_SAMPLE_RATE", "0.0"))
        except ValueError:
            sample_rate = 0.0
        try:
            return SafeTelemetryAdapter(LangSmithTelemetryAdapter(api_key=api_key, project=os.getenv("LANGSMITH_PROJECT", "cityscope"), sample_rate=sample_rate))
        except Exception:
            LOGGER.warning("LangSmith telemetry could not initialize; telemetry is off", exc_info=False)
            return SafeTelemetryAdapter(OffTelemetryAdapter())
    if mode != "local":
        LOGGER.warning("Unknown CITYSCOPE_TELEMETRY mode; using local telemetry")
    return SafeTelemetryAdapter(LocalTelemetryAdapter())
