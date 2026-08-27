from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


LiveCityId = Literal["new_york", "chicago", "washington_dc", "paris"]


class LiveStationRequest(BaseModel):
    city: LiveCityId = "paris"
    limit: int = Field(default=25, ge=1, le=100)


class LiveStation(BaseModel):
    station_id: str
    name: str | None = None
    latitude: float
    longitude: float
    bikes_available: int = Field(ge=0)
    docks_available: int = Field(ge=0)
    last_reported: int | None = None


class LiveNetworkResponse(BaseModel):
    city: LiveCityId
    provider: str
    provider_timestamp: int | None = None
    fetched_at: str
    freshness: Literal["fresh", "delayed", "stale", "unknown"]
    attribution_text: str
    source_url: str
    stations: list[LiveStation]
    limitations: list[str]
