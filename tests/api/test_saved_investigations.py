from fastapi.testclient import TestClient

from apps.api.app.auth import CurrentUser, get_current_user
from apps.api.app.history import InMemoryInvestigationStore, get_history_store
from apps.api.app.main import app


def payload(question: str = "Where are the cycling hotspots?") -> dict:
    return {
        "request": {"city": "london", "question": question, "context": {"selected_h3_cells": [], "previous_turns": []}},
        "result": {
            "investigation_id": "source-result", "status": "answered", "answer": "Historical activity is highest near King's Cross.",
            "dataset": {"city": "london", "dataset_id": "tfl", "dataset_name": "TfL Cycling", "snapshot_id": "2026-05", "observation_start": "2026-05-01", "observation_end": "2026-06-01", "source_organisation": "TfL", "mode": "cycle_hire", "h3_resolution": 9, "historical": True, "available_metrics": ["starts"], "supported_temporal_filters": [], "limitations": [], "provenance_summary": {}},
            "evidence": [{"source": "city_data", "metric": "starts", "value": 42, "unit": "journeys", "source_aggregate": "canonical", "h3_cells": ["89194ad3353ffff"], "filters_applied": {}}],
            "places": [{"place_id": "place-should-not-persist", "name": "Current cafe", "latitude": 51.5, "longitude": -0.1, "category": "cafe", "h3_cell": "89194ad3353ffff"}],
            "route": {"travel_mode": "bicycle", "distance_m": 1200, "duration_seconds": 600, "polyline": "must-not-persist", "source": "google_routes_api", "warning": "Check conditions", "origin": {"name": "A", "latitude": 51.5, "longitude": -0.1}, "destination": {"name": "B", "latitude": 51.51, "longitude": -0.11}, "waypoints": []},
            "amenity_analysis": [], "city_insights": [], "map_layers": [], "limitations": [], "trace": [], "follow_up_suggestions": [],
        },
    }


def test_saved_investigations_are_private_and_exclude_current_provider_data():
    store = InMemoryInvestigationStore()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(uid="judge-a")
    app.dependency_overrides[get_history_store] = lambda: store
    client = TestClient(app)
    try:
        created = client.post("/me/investigations", json=payload())
        assert created.status_code == 201
        record = created.json()
        assert record["question"] == "Where are the cycling hotspots?"
        assert record["historical_evidence"][0]["value"] == 42
        assert "places" not in record
        assert "route" not in record
        assert "must-not-persist" not in created.text

        assert client.get("/me/investigations").json()[0]["id"] == record["id"]
        assert client.delete(f"/me/investigations/{record['id']}").status_code == 204
        assert client.get("/me/investigations").json() == []
    finally:
        app.dependency_overrides.clear()


def test_saved_investigations_require_a_verified_identity():
    client = TestClient(app)
    response = client.get("/me/investigations")
    assert response.status_code == 401

