from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from .schemas import LiveCityId, LiveNetworkResponse, LiveStation, LiveStationRequest


VELIB_STATUS_URL = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json"
VELIB_INFORMATION_URL = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_information.json"


@dataclass(frozen=True)
class LiveProvider:
    city: LiveCityId
    provider: str
    status_url: str
    information_url: str
    attribution_text: str


LIVE_PROVIDERS: dict[LiveCityId, LiveProvider] = {
    "new_york": LiveProvider("new_york", "Citi Bike GBFS", "https://gbfs.lyft.com/gbfs/2.3/bkn/en/station_status.json", "https://gbfs.lyft.com/gbfs/2.3/bkn/en/station_information.json", "Live station status provided by Citi Bike."),
    "chicago": LiveProvider("chicago", "Divvy GBFS", "https://gbfs.lyft.com/gbfs/2.3/chi/en/station_status.json", "https://gbfs.lyft.com/gbfs/2.3/chi/en/station_information.json", "Live station status provided by Divvy."),
    "washington_dc": LiveProvider("washington_dc", "Capital Bikeshare GBFS", "https://gbfs.lyft.com/gbfs/2.3/dca-cabi/en/station_status.json", "https://gbfs.lyft.com/gbfs/2.3/dca-cabi/en/station_information.json", "Live station status provided by Capital Bikeshare."),
    "paris": LiveProvider("paris", "Vélib' Métropole GBFS", VELIB_STATUS_URL, VELIB_INFORMATION_URL, "Live station status provided by Vélib' Métropole."),
}


class GbfsClient:
    def __init__(self, city: LiveCityId, url: str | None = None, information_url: str | None = None, timeout_s: float = 12.0) -> None:
        self.provider = LIVE_PROVIDERS[city]
        self.url = url or self.provider.status_url
        self.information_url = information_url or self.provider.information_url
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
            raise ValueError(f"{self.provider.provider} response is malformed")
        provider_timestamp = _int_or_none(payload.get("lastUpdatedOther") or payload.get("last_updated"))
        information = {str(raw.get("station_id")): raw for raw in information_payload["data"]["stations"] if isinstance(raw, dict)}
        parsed_stations = [_station(raw, information.get(str(raw.get("station_id")))) for raw in payload["data"]["stations"]]
        stations = list({station.station_id: station for station in parsed_stations if station is not None}.values())
        stations.sort(key=_station_display_sort_key)
        now = datetime.now(UTC)
        return LiveNetworkResponse(
            city=self.provider.city, provider=self.provider.provider, provider_timestamp=provider_timestamp, fetched_at=now.isoformat(),
            freshness=_freshness(provider_timestamp, now.timestamp()), attribution_text=self.provider.attribution_text, source_url=self.url,
            stations=stations if limit is None else stations[:limit], limitations=["Live station availability is operational context, not historical trip demand.", "Live network data is not included in cross-city historical comparisons."],
        )


class VelibClient(GbfsClient):
    """Compatibility wrapper retained for the Paris archive job."""

    def __init__(self, url: str | None = None, information_url: str | None = None, timeout_s: float = 12.0) -> None:
        super().__init__("paris", url, information_url, timeout_s)


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
    return await GbfsClient(request.city).get_status(request.limit)
