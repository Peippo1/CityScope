from __future__ import annotations

from datetime import UTC, datetime
import os
from typing import Any

import httpx

from .schemas import LiveNetworkResponse, LiveStation, LiveStationRequest


VELIB_STATUS_URL = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json"


class VelibClient:
    def __init__(self, url: str | None = None, timeout_s: float = 12.0) -> None:
        self.url = url or os.getenv("CITYSCOPE_VELIB_STATUS_URL", VELIB_STATUS_URL)
        self.timeout_s = timeout_s

    async def get_status(self, limit: int) -> LiveNetworkResponse:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.get(self.url, headers={"accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict) or not isinstance(payload["data"].get("stations"), list):
            raise ValueError("Vélib' GBFS response is malformed")
        provider_timestamp = _int_or_none(payload.get("last_updated"))
        stations = [_station(raw) for raw in payload["data"]["stations"]]
        stations = [station for station in stations if station is not None]
        stations.sort(key=lambda station: (station.bikes_available, station.station_id))
        now = datetime.now(UTC)
        return LiveNetworkResponse(
            city="paris", provider="Vélib' Métropole GBFS", provider_timestamp=provider_timestamp, fetched_at=now.isoformat(),
            freshness=_freshness(provider_timestamp, now.timestamp()), attribution_text="Live station status provided by Vélib' Métropole.", source_url=self.url,
            stations=stations[:limit], limitations=["Live station availability is operational context, not historical trip demand.", "Paris live data is not included in cross-city historical comparisons."],
        )


def _int_or_none(value: Any) -> int | None:
    try: return int(value)
    except (TypeError, ValueError): return None


def _station(raw: Any) -> LiveStation | None:
    if not isinstance(raw, dict): return None
    station_id = raw.get("station_id")
    latitude, longitude = raw.get("lat"), raw.get("lon")
    bikes, docks = raw.get("num_bikes_available"), raw.get("num_docks_available")
    if not isinstance(station_id, (str, int)) or not all(isinstance(value, (int, float)) for value in (latitude, longitude, bikes, docks)): return None
    if not (-90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180 and bikes >= 0 and docks >= 0): return None
    return LiveStation(station_id=str(station_id), name=raw.get("name") if isinstance(raw.get("name"), str) else None, latitude=float(latitude), longitude=float(longitude), bikes_available=int(bikes), docks_available=int(docks), last_reported=_int_or_none(raw.get("last_reported")))


def _freshness(provider_timestamp: int | None, now: float) -> str:
    if provider_timestamp is None: return "unknown"
    age = max(0, now - provider_timestamp)
    return "fresh" if age <= 300 else "delayed" if age <= 1800 else "stale"


async def get_live_station_status(request: LiveStationRequest) -> LiveNetworkResponse:
    return await VelibClient().get_status(request.limit)
