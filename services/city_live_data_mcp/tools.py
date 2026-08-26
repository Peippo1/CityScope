from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import os
from typing import Any

import httpx

from .schemas import LiveNetworkResponse, LiveStation, LiveStationRequest


VELIB_STATUS_URL = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json"
VELIB_INFORMATION_URL = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_information.json"


class VelibClient:
    def __init__(self, url: str | None = None, information_url: str | None = None, timeout_s: float = 12.0) -> None:
        self.url = url or os.getenv("CITYSCOPE_VELIB_STATUS_URL", VELIB_STATUS_URL)
        self.information_url = information_url or os.getenv("CITYSCOPE_VELIB_INFORMATION_URL", VELIB_INFORMATION_URL)
        self.timeout_s = timeout_s

    async def get_status(self, limit: int | None) -> LiveNetworkResponse:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            status_response, information_response = await asyncio.gather(
                client.get(self.url, headers={"accept": "application/json"}),
                client.get(self.information_url, headers={"accept": "application/json"}),
            )
        status_response.raise_for_status()
        information_response.raise_for_status()
        payload, information_payload = status_response.json(), information_response.json()
        if not _valid_payload(payload) or not _valid_payload(information_payload):
            raise ValueError("Vélib' GBFS response is malformed")
        provider_timestamp = _int_or_none(payload.get("lastUpdatedOther") or payload.get("last_updated"))
        information = {str(raw.get("station_id")): raw for raw in information_payload["data"]["stations"] if isinstance(raw, dict)}
        stations = [_station(raw, information.get(str(raw.get("station_id")))) for raw in payload["data"]["stations"]]
        stations = [station for station in stations if station is not None]
        stations.sort(key=_station_display_sort_key)
        now = datetime.now(UTC)
        return LiveNetworkResponse(
            city="paris", provider="Vélib' Métropole GBFS", provider_timestamp=provider_timestamp, fetched_at=now.isoformat(),
            freshness=_freshness(provider_timestamp, now.timestamp()), attribution_text="Live station status provided by Vélib' Métropole.", source_url=self.url,
            stations=stations if limit is None else stations[:limit], limitations=["Live station availability is operational context, not historical trip demand.", "Paris live data is not included in cross-city historical comparisons."],
        )


def _valid_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("stations"), list)


def _int_or_none(value: Any) -> int | None:
    try: return int(value)
    except (TypeError, ValueError): return None


def _station(raw: Any, information: Any = None) -> LiveStation | None:
    if not isinstance(raw, dict) or (information is not None and not isinstance(information, dict)): return None
    raw = {**(information or {}), **raw}
    station_id = raw.get("station_id")
    latitude, longitude = raw.get("lat"), raw.get("lon")
    bikes, docks = raw.get("num_bikes_available"), raw.get("num_docks_available")
    if not isinstance(station_id, (str, int)) or not all(isinstance(value, (int, float)) for value in (latitude, longitude, bikes, docks)): return None
    if not (-90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180 and bikes >= 0 and docks >= 0): return None
    return LiveStation(station_id=str(station_id), name=raw.get("name") if isinstance(raw.get("name"), str) else None, latitude=float(latitude), longitude=float(longitude), bikes_available=int(bikes), docks_available=int(docks), last_reported=_int_or_none(raw.get("last_reported")))


def _station_display_sort_key(station: LiveStation) -> tuple[int, int, str]:
    return (-station.bikes_available, -station.docks_available, station.station_id)


def _freshness(provider_timestamp: int | None, now: float) -> str:
    if provider_timestamp is None: return "unknown"
    age = max(0, now - provider_timestamp)
    return "fresh" if age <= 300 else "delayed" if age <= 1800 else "stale"


async def get_live_station_status(request: LiveStationRequest) -> LiveNetworkResponse:
    return await VelibClient().get_status(request.limit)
