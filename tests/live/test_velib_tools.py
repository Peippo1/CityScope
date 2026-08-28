import pytest

from services.city_live_data_mcp.schemas import LiveStationRequest
from services.city_live_data_mcp.tools import LIVE_PROVIDERS, _freshness, _station, _station_display_sort_key


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


def test_velib_display_prioritizes_stations_with_available_bikes():
    stations = [
        _station({"station_id": "empty", "lat": 48.85, "lon": 2.35, "num_bikes_available": 0, "num_docks_available": 20}),
        _station({"station_id": "useful", "lat": 48.86, "lon": 2.36, "num_bikes_available": 8, "num_docks_available": 4}),
        _station({"station_id": "fuller", "lat": 48.87, "lon": 2.37, "num_bikes_available": 8, "num_docks_available": 12}),
    ]

    assert [station.station_id for station in sorted(stations, key=_station_display_sort_key)] == ["fuller", "useful", "empty"]


def test_live_provider_registry_uses_only_fixed_https_gbfs_endpoints():
    assert set(LIVE_PROVIDERS) == {"new_york", "chicago", "washington_dc", "paris"}
    for provider in LIVE_PROVIDERS.values():
        assert provider.status_url.startswith("https://")
        assert provider.information_url.startswith("https://")
        assert "station_status.json" in provider.status_url
        assert "station_information.json" in provider.information_url
