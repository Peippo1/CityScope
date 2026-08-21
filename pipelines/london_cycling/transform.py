from pathlib import Path

import pandas as pd
from h3 import latlng_to_cell

from .schema import CyclingJourney

PRIMARY_H3_RESOLUTION = 9


def read_and_transform(source: Path, resolution: int = PRIMARY_H3_RESOLUTION) -> pd.DataFrame:
    raw = pd.read_csv(source)
    journeys = [CyclingJourney.model_validate(row.to_dict()) for _, row in raw.iterrows()]
    frame = pd.DataFrame([journey.model_dump() for journey in journeys])
    frame["start_timestamp"] = pd.to_datetime(frame["start_timestamp"], utc=True)
    frame["end_timestamp"] = pd.to_datetime(frame["end_timestamp"], utc=True)
    frame["hour"] = frame["start_timestamp"].dt.hour
    frame["weekday"] = frame["start_timestamp"].dt.day_name()
    frame["is_weekend"] = frame["start_timestamp"].dt.dayofweek >= 5
    frame["month"] = frame["start_timestamp"].dt.month
    frame["time_of_day"] = frame["hour"].map(_time_of_day)
    frame["origin_h3"] = [
        latlng_to_cell(lat, lon, resolution)
        for lat, lon in zip(frame["origin_latitude"], frame["origin_longitude"])
    ]
    frame["destination_h3"] = [
        latlng_to_cell(lat, lon, resolution)
        for lat, lon in zip(frame["destination_latitude"], frame["destination_longitude"])
    ]
    return frame


def build_activity_aggregate(journeys: pd.DataFrame) -> pd.DataFrame:
    origins = journeys[["origin_h3", "journey_id"]].rename(columns={"origin_h3": "h3_cell"})
    destinations = journeys[["destination_h3", "journey_id"]].rename(columns={"destination_h3": "h3_cell"})
    activity = pd.concat([origins, destinations]).groupby("h3_cell", as_index=False).agg(
        total_journeys=("journey_id", "count")
    )
    origin_counts = origins.groupby("h3_cell").size().rename("origin_journeys")
    destination_counts = destinations.groupby("h3_cell").size().rename("destination_journeys")
    activity = activity.join(origin_counts, on="h3_cell").join(destination_counts, on="h3_cell").fillna(0)
    activity["origin_journeys"] = activity["origin_journeys"].astype(int)
    activity["destination_journeys"] = activity["destination_journeys"].astype(int)
    return activity.sort_values(["total_journeys", "h3_cell"], ascending=[False, True]).reset_index(drop=True)


def _time_of_day(hour: int) -> str:
    if hour < 6:
        return "night"
    if hour < 9:
        return "morning_commute"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "midday"
    if hour < 20:
        return "evening_commute"
    return "evening"
