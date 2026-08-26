from __future__ import annotations

import pandas as pd

from pipelines.core.spatial import add_h3_cells
from pipelines.core.temporal import add_temporal_features


REQUIRED = {"ride_id", "started_at", "ended_at", "start_station_id", "end_station_id", "start_lat", "start_lng", "end_lat", "end_lng"}


def to_canonical(source: pd.DataFrame, resolution: int = 9) -> pd.DataFrame:
    missing = REQUIRED - set(source.columns)
    if missing: raise ValueError(f"Divvy source is missing columns: {sorted(missing)}")
    start, end = pd.to_datetime(source["started_at"], utc=True), pd.to_datetime(source["ended_at"], utc=True)
    frame = pd.DataFrame({"city": "chicago", "dataset_id": "divvy-trips", "snapshot_id": "2026-05", "mode": "cycle_hire", "trip_id": source["ride_id"].astype(str), "origin_location_id": source["start_station_id"].astype(str), "destination_location_id": source["end_station_id"].astype(str), "origin_latitude": source["start_lat"], "origin_longitude": source["start_lng"], "destination_latitude": source["end_lat"], "destination_longitude": source["end_lng"], "start_timestamp": start, "end_timestamp": end, "duration_seconds": (end - start).dt.total_seconds(), "source_properties_json": source.reindex(columns=["rideable_type", "member_casual"]).fillna("").apply(lambda row: row.to_json(), axis=1)})
    return add_h3_cells(add_temporal_features(frame), resolution)
