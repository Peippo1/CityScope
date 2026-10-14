import asyncio
from collections import deque

import pytest
from fastapi import HTTPException, Request

from apps.api.app import config
from apps.api.app.admission import InvestigationAdmission, _ClientWindow, admission
from apps.api.app.main import app
from .client import ApiClient


def setup_function():
    admission.reset()


def test_api_adds_security_headers_and_rejects_oversized_request(monkeypatch):
    monkeypatch.setattr(config, "MAX_REQUEST_BYTES", 40)
    client = ApiClient(app)

    response = client.post("/investigate", content="x" * 41, headers={"content-type": "application/json"})

    assert response.status_code == 413
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


def test_investigation_rate_limit_returns_retry_after(monkeypatch):
    monkeypatch.setattr(config, "INVESTIGATION_RATE_LIMIT", 1)
    client = ApiClient(app)
    payload = {"city": "rome", "question": "What are the hotspots?"}

    first = client.post("/investigate", json=payload)
    second = client.post("/investigate", json=payload)

    assert first.status_code == 422
    assert second.status_code == 429
    assert second.headers["retry-after"]


def test_investigation_request_rejects_unexpected_fields():
    response = ApiClient(app).post("/investigate", json={"question": "Where are the hotspots?", "untrusted": "value"})

    assert response.status_code == 422


def test_stale_client_entries_are_evicted_before_new_clients_are_tracked(monkeypatch):
    limiter = InvestigationAdmission()
    limiter._clients = {"stale": _ClientWindow(deque([0.0]))}
    monkeypatch.setattr("apps.api.app.admission.time.monotonic", lambda: 301.0)

    request = Request({"type": "http", "client": ("new-client", 1234), "headers": []})
    lease = asyncio.run(limiter.acquire(request))

    assert "stale" not in limiter._clients
    assert "new-client" in limiter._clients
    asyncio.run(lease.__aexit__(None, None, None))


def test_tracked_client_limit_bounds_rotating_source_addresses(monkeypatch):
    limiter = InvestigationAdmission()
    limiter.max_tracked_clients = 1
    limiter._clients = {"existing": _ClientWindow(deque([300.0]))}
    monkeypatch.setattr("apps.api.app.admission.time.monotonic", lambda: 300.0)

    request = Request({"type": "http", "client": ("rotating-client", 1234), "headers": []})
    with pytest.raises(HTTPException) as error:
        asyncio.run(limiter.acquire(request))

    assert error.value.status_code == 429
