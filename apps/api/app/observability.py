from __future__ import annotations

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from typing import Any


LOGGER = logging.getLogger("cityscope.observability")
_REQUEST_ID: ContextVar[str] = ContextVar("cityscope_request_id", default="")
_ACTIVITY: ContextVar[str] = ContextVar("cityscope_activity", default="")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def new_request_id(candidate: str | None = None) -> str:
    """Accept a bounded correlation token, otherwise generate an opaque ID."""
    return candidate if candidate and _REQUEST_ID_PATTERN.fullmatch(candidate) else str(uuid.uuid4())


def set_request_context(request_id: str, activity: str | None = None) -> tuple[Any, Any]:
    return _REQUEST_ID.set(request_id), _ACTIVITY.set(activity or "")


def reset_request_context(tokens: tuple[Any, Any]) -> None:
    _REQUEST_ID.reset(tokens[0])
    _ACTIVITY.reset(tokens[1])


def request_id() -> str | None:
    return _REQUEST_ID.get() or None


def activity() -> str | None:
    return _ACTIVITY.get() or None


def emit_event(event: str, **fields: object) -> None:
    """Emit Cloud Logging-compatible JSON without request content or secrets."""
    payload: dict[str, object] = {"event": event}
    if request_id():
        payload["request_id"] = request_id()
    if activity():
        payload["activity"] = activity()
    payload.update({key: value for key, value in fields.items() if value is not None})
    LOGGER.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
