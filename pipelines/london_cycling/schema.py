from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CyclingJourney(BaseModel):
    model_config = ConfigDict(extra="forbid")

    journey_id: str = Field(min_length=1)
    start_timestamp: datetime
    end_timestamp: datetime
    duration_seconds: int = Field(gt=0)
    origin_station_id: str = Field(min_length=1)
    destination_station_id: str = Field(min_length=1)
    origin_latitude: float = Field(ge=-90, le=90)
    origin_longitude: float = Field(ge=-180, le=180)
    destination_latitude: float = Field(ge=-90, le=90)
    destination_longitude: float = Field(ge=-180, le=180)

    @field_validator("end_timestamp")
    @classmethod
    def end_after_start(cls, value: datetime, info):
        start = info.data.get("start_timestamp")
        if start and value <= start:
            raise ValueError("end_timestamp must be after start_timestamp")
        return value
