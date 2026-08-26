from pathlib import Path

from fastapi.testclient import TestClient

from pipelines.london_cycling.build_fixture import main as build_fixture
from apps.api.app import config
from apps.api.app.main import app


def test_london_activity_endpoint_returns_typed_h3_activity():
    build_fixture()
    response = TestClient(app).get("/cities/london/activity?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["city"] == "london"
    assert payload["observation_period"] in {"2024-01-06/2024-01-08", "2026-05-01/2026-05-31"}
    assert payload["historical_snapshot"] is True
    assert len(payload["cells"]) == 2
    assert payload["cells"][0]["total_journeys"] >= payload["cells"][1]["total_journeys"]


def test_unknown_city_is_rejected():
    response = TestClient(app).get("/cities/paris/activity")

    assert response.status_code == 404


def test_activity_limit_is_validated():
    response = TestClient(app).get("/cities/london/activity?limit=0")

    assert response.status_code == 422


def test_local_nextjs_fallback_port_is_allowed_by_cors():
    response = TestClient(app).get(
        "/cities/london/activity?limit=1",
        headers={"Origin": "http://localhost:3001"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"


def test_production_origin_does_not_enable_local_cors_regex(monkeypatch):
    monkeypatch.setenv("CITYSCOPE_WEB_ORIGIN", "https://cityscope.example")

    assert config.configured_origin_regex() is None


def test_investigation_request_rejects_unsupported_city_before_agent_execution():
    response = TestClient(app).post("/investigate", json={"city": "paris", "question": "What are the hotspots?"})

    assert response.status_code == 422


def test_health_reports_configuration_without_secret_values(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_GROUNDING_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_ROUTES_API_KEY", raising=False)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "missing_configuration": "GEMINI_API_KEY, GOOGLE_MAPS_GROUNDING_API_KEY or GOOGLE_MAPS_API_KEY, GOOGLE_ROUTES_API_KEY or GOOGLE_MAPS_API_KEY",
    }
    assert "AIza" not in response.text
