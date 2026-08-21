import pandas as pd

from pipelines.core.spatial import add_h3_cells
from pipelines.core.temporal import add_temporal_features


def to_canonical(source: pd.DataFrame, resolution: int = 9) -> pd.DataFrame:
    result = pd.DataFrame({
        "city": "new_york",
        "dataset_id": "citibike-trip-history",
        "snapshot_id": "fixture",
        "mode": "cycle_hire",
        "trip_id": source["ride_id"].astype(str),
        "origin_location_id": source["start_station_id"].astype(str),
        "destination_location_id": source["end_station_id"].astype(str),
        "origin_latitude": source["start_lat"].astype(float),
        "origin_longitude": source["start_lng"].astype(float),
        "destination_latitude": source["end_lat"].astype(float),
        "destination_longitude": source["end_lng"].astype(float),
        "start_timestamp": pd.to_datetime(source["started_at"], utc=True),
        "end_timestamp": pd.to_datetime(source["ended_at"], utc=True),
        "duration_seconds": (pd.to_datetime(source["ended_at"], utc=True) - pd.to_datetime(source["started_at"], utc=True)).dt.total_seconds().astype(int),
        "source_properties_json": source[["rideable_type", "member_casual"]].apply(lambda row: row.to_json(), axis=1),
    })
    return add_h3_cells(add_temporal_features(result), resolution)
