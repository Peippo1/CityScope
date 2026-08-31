from pathlib import Path

import pytest

from pipelines.london_cycling.build_fixture import main as build_fixture
from pipelines.multicity.build_fixture import main as build_multicity_fixture
from apps.api.app import config
from apps.api.app.main import app
from apps.api.app.agent.live_mcp_client import CityLiveMcpClient
from apps.api.app.routes.cities import ANALYTICS
from .client import ApiClient


@pytest.fixture(scope="module", autouse=True)
def city_fixtures():
    build_fixture()
    build_multicity_fixture()


def test_london_activity_endpoint_returns_typed_h3_activity():
    response = ApiClient(app).get("/cities/london/activity?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["city"] == "london"
    assert payload["observation_period"] in {"2024-01-06/2024-01-08", "2026-05-01/2026-05-31"}
    assert payload["historical_snapshot"] is True
    assert len(payload["cells"]) == 2
    assert payload["cells"][0]["area_name"]
    assert payload["cells"][0]["total_journeys"] >= payload["cells"][1]["total_journeys"]


def test_activity_endpoint_default_limit_stays_within_h3_query_bound():
    response = ApiClient(app).get("/cities/london/activity")

    assert response.status_code == 200
    assert len(response.json()["cells"]) <= 50


def test_city_registry_and_normalized_comparison_endpoint():
    client = ApiClient(app)
    cities = client.get("/cities")
    comparison = client.get("/cities/compare?metric=weekend_share")

    assert cities.status_code == 200
    assert {city["id"] for city in cities.json()["cities"]} == {"london", "new_york", "chicago", "washington_dc", "paris", "copenhagen", "barcelona", "madrid"}
    assert comparison.status_code == 200
    assert comparison.json()["metric"] == "weekend_share"
    assert len(comparison.json()["cities"]) == 4
    live_cities = {city["id"] for city in cities.json()["cities"] if city["live_network"]}
    assert live_cities == {"new_york", "chicago", "washington_dc", "paris"}


@pytest.mark.parametrize("city", ["london", "new_york", "chicago", "washington_dc"])
def test_every_historical_city_exposes_activity(city):
    response = ApiClient(app).get(f"/cities/{city}/activity?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["city"] == city
    assert payload["historical_snapshot"] is True
    assert len(payload["cells"]) == 1


def test_cross_city_endpoint_rejects_raw_counts():
    response = ApiClient(app).get("/cities/compare?metric=total_activity")
    assert response.status_code == 422


def test_cross_city_runtime_failure_is_sanitized(monkeypatch):
    monkeypatch.setattr(ANALYTICS, "compare_cities", lambda *_: (_ for _ in ()).throw(RuntimeError("private database path")))

    response = ApiClient(app).get("/cities/compare?metric=weekend_share")

    assert response.status_code == 503
    assert response.json()["detail"] == "Cross-city comparison is temporarily unavailable"
    assert "private database path" not in response.text


def test_unknown_city_is_rejected():
    response = ApiClient(app).get("/cities/paris/activity")

    assert response.status_code == 404


@pytest.mark.parametrize("city", ["new_york", "chicago", "washington_dc", "paris"])
def test_live_network_endpoint_dispatches_to_the_selected_fixed_provider(monkeypatch, city):
    async def fake_status(self, selected_city, limit):
        return {"city": selected_city, "stations": [], "limit": limit}

    monkeypatch.setattr(CityLiveMcpClient, "get_status", fake_status)
    response = ApiClient(app).get(f"/cities/{city}/live-network?limit=7")

    assert response.status_code == 200
    assert response.json() == {"city": city, "stations": [], "limit": 7}


def test_live_network_endpoint_rejects_a_historical_only_city():
    response = ApiClient(app).get("/cities/london/live-network")

    assert response.status_code == 404


def test_live_network_endpoint_rejects_an_unknown_city():
    response = ApiClient(app).get("/cities/berlin/live-network")

    assert response.status_code == 404


def test_activity_limit_is_validated():
    response = ApiClient(app).get("/cities/london/activity?limit=0")

    assert response.status_code == 422


def test_local_nextjs_fallback_port_is_allowed_by_cors():
    response = ApiClient(app).get(
        "/cities/london/activity?limit=1",
        headers={"Origin": "http://localhost:3001"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"


def test_production_origin_does_not_enable_local_cors_regex(monkeypatch):
    monkeypatch.setenv("CITYSCOPE_WEB_ORIGIN", "https://cityscope.example")

    assert config.configured_origin_regex() is None


def test_investigation_request_rejects_unknown_city_before_agent_execution():
    response = ApiClient(app).post("/investigate", json={"city": "rome", "question": "What are the hotspots?"})

    assert response.status_code == 422


def test_health_reports_configuration_without_secret_values(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_GROUNDING_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_ROUTES_API_KEY", raising=False)

    response = ApiClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "missing_configuration": "GEMINI_API_KEY, GOOGLE_MAPS_GROUNDING_API_KEY or GOOGLE_MAPS_API_KEY, GOOGLE_ROUTES_API_KEY or GOOGLE_MAPS_API_KEY",
    }
    assert "AIza" not in response.text
