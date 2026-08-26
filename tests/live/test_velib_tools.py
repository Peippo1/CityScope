from services.city_live_data_mcp.tools import _freshness, _station


def test_velib_station_validation_rejects_malformed_provider_rows():
    assert _station({"station_id": "bad", "lat": 200, "lon": 2, "num_bikes_available": 1, "num_docks_available": 1}) is None
    assert _station({"station_id": "1", "lat": 48.85, "lon": 2.35, "num_bikes_available": 3, "num_docks_available": 4}).bikes_available == 3


def test_velib_station_status_joins_information_coordinates():
    station = _station(
        {"station_id": 1, "num_bikes_available": 3, "num_docks_available": 4, "last_reported": 1000},
        {"station_id": 1, "name": "Hôtel de Ville", "lat": 48.8566, "lon": 2.3522},
    )

    assert station.name == "Hôtel de Ville"
    assert station.latitude == 48.8566


def test_velib_freshness_is_explicit():
    assert _freshness(1000, 1100) == "fresh"
    assert _freshness(1000, 1400) == "delayed"
    assert _freshness(1000, 4000) == "stale"
    assert _freshness(None, 4000) == "unknown"
