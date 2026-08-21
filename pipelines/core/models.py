from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Coordinate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Provenance(BaseModel):
    source_organisation: str
    source_url: str
    source_file: str
    source_checksum_sha256: str


class DatasetSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str = Field(min_length=2)
    dataset_id: str = Field(min_length=2)
    snapshot_id: str = Field(min_length=2)
    mode: str = Field(min_length=2)
    observation_start: datetime
    observation_end: datetime
    provenance: list[Provenance]
    h3_resolution: int = Field(ge=0, le=15)


class MobilityTrip(BaseModel):
    model_config = ConfigDict(extra="allow")

    city: str
    dataset_id: str
    snapshot_id: str
    mode: str
    trip_id: str
    origin_location_id: str
    destination_location_id: str
    origin: Coordinate
    destination: Coordinate
    start_timestamp: datetime
    end_timestamp: datetime
    duration_seconds: int = Field(gt=0)
    source_properties: dict[str, Any] = Field(default_factory=dict)
