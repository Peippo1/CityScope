from apps.api.app.auth import CurrentUser, get_current_user
from apps.api.app.history import FirestoreInvestigationStore, InMemoryInvestigationStore, SavedInvestigationCreate, get_history_store
from apps.api.app.main import app
from .client import ApiClient


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
    client = ApiClient(app)
    try:
        created = client.post("/me/investigations", json=payload())
        assert created.status_code == 201
        record = created.json()
        assert record["record_type"] == "historical_investigation"
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
    client = ApiClient(app)
    response = client.get("/me/investigations")
    assert response.status_code == 401


def test_live_network_payloads_cannot_be_saved():
    store = InMemoryInvestigationStore()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(uid="judge-a")
    app.dependency_overrides[get_history_store] = lambda: store
    live_payload = payload()
    live_payload["request"]["city"] = "paris"
    live_payload["result"]["city_insights"] = [{"stations": [{"station_id": "live"}]}]
    client = ApiClient(app)
    try:
        response = client.post("/me/investigations", json=live_payload)
        assert response.status_code == 422
        assert response.json()["detail"] == "Live network availability is ephemeral and cannot be saved as an investigation."
    finally:
        app.dependency_overrides.clear()


def test_cross_city_comparisons_have_an_explicit_saved_record_type():
    comparison_payload = payload("How do the four cities compare?")
    comparison_payload["result"]["evidence"] = [{
        "source": "city_data", "metric": "hotspot_concentration", "value": 0.8, "unit": "share",
        "source_aggregate": "cross_city_canonical_trips", "filters_applied": {}, "h3_cells": [], "category": "Chicago",
    }]

    record = InMemoryInvestigationStore().create(CurrentUser(uid="judge-a"), SavedInvestigationCreate.model_validate(comparison_payload))

    assert record.record_type == "historical_comparison"
    assert record.comparison_metric == "hotspot_concentration"
    assert record.comparison_cities == ["Chicago"]


def test_firestore_operations_use_bounded_deadlines():
    calls: list[tuple[str, float | None]] = []

    class Snapshot:
        exists = True

        def to_dict(self):
            return {"owner_uid": "judge-a", **created.model_dump(mode="json")}

    class Document:
        id = "firestore-record"

        def set(self, value, timeout=None):
            calls.append(("set", timeout))

        def get(self, timeout=None):
            calls.append(("get", timeout))
            return Snapshot()

        def delete(self, timeout=None):
            calls.append(("delete", timeout))

    class Collection:
        def document(self, investigation_id=None):
            return Document()

        def where(self, *args, **kwargs):
            return self

        def stream(self, timeout=None):
            calls.append(("stream", timeout))
            return iter([Snapshot()])

    class Client:
        def collection(self, name):
            return Collection()

    store = FirestoreInvestigationStore.__new__(FirestoreInvestigationStore)
    store.client = Client()
    user = CurrentUser(uid="judge-a")
    saved_payload = SavedInvestigationCreate.model_validate(payload())
    created = store.create(user, saved_payload)

    assert store.list(user)
    assert store.get(user, created.id)
    assert store.delete(user, created.id) is True
    assert calls == [("set", 10.0), ("stream", 10.0), ("get", 10.0), ("get", 10.0), ("delete", 10.0)]
