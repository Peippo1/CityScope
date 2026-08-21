from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

MetricName = Literal["starts", "ends", "total_activity", "journey_count", "city_percentile"]
TimeOfDay = Literal["night", "morning_commute", "morning", "midday", "evening_commute", "evening"]
Weekday = Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TimeFilter(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    weekdays: list[Weekday] = Field(default_factory=list, max_length=7)
    hour_start: int | None = Field(default=None, ge=0, le=23)
    hour_end: int | None = Field(default=None, ge=1, le=24)
    weekend: bool | None = None
    time_of_day: list[TimeOfDay] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        if self.hour_start is not None and self.hour_end is not None and self.hour_end <= self.hour_start:
            raise ValueError("hour_end must be greater than hour_start")
        return self
