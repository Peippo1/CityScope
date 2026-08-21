from pathlib import Path

from fastapi.testclient import TestClient

from pipelines.london_cycling.build_fixture import main as build_fixture
from apps.api.app.main import app


def test_london_activity_endpoint_returns_typed_h3_activity():
    build_fixture()
    response = TestClient(app).get("/cities/london/activity?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["city"] == "london"
    assert payload["observation_period"] == "2024-01-06/2024-01-08"
    assert len(payload["cells"]) == 2
    assert payload["cells"][0]["total_journeys"] >= payload["cells"][1]["total_journeys"]


def test_unknown_city_is_rejected():
    response = TestClient(app).get("/cities/paris/activity")

    assert response.status_code == 404


def test_activity_limit_is_validated():
    response = TestClient(app).get("/cities/london/activity?limit=0")

    assert response.status_code == 422
