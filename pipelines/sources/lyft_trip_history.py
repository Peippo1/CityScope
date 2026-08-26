from __future__ import annotations

from dataclasses import dataclass
import json

import pandas as pd
from h3 import is_valid_cell

from pipelines.core.spatial import add_h3_cells
from pipelines.core.temporal import add_temporal_features


REQUIRED_COLUMNS = {
    "ride_id", "started_at", "ended_at", "start_station_id", "end_station_id",
    "start_lat", "start_lng", "end_lat", "end_lng",
}


@dataclass(frozen=True)
class SourceConfig:
    city: str
    dataset_id: str
    timezone: str
    bounds: tuple[float, float, float, float]


def _local_timestamp(values: pd.Series, timezone: str) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce")
    if parsed.dt.tz is None:
        return parsed.dt.tz_localize(timezone, ambiguous="NaT", nonexistent="NaT")
    return parsed.dt.tz_convert(timezone)


def transform_trip_history(source: pd.DataFrame, config: SourceConfig, *, enforce_may_2026: bool, resolution: int = 9) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = REQUIRED_COLUMNS - set(source.columns)
    if missing:
        raise ValueError(f"{config.city} source is missing columns: {sorted(missing)}")

    working = source.copy()
    start_local = _local_timestamp(working["started_at"], config.timezone)
    end_local = _local_timestamp(working["ended_at"], config.timezone)
    coordinates = working[["start_lat", "start_lng", "end_lat", "end_lng"]].apply(pd.to_numeric, errors="coerce")
    durations = (end_local - start_local).dt.total_seconds()
    reasons = pd.Series(pd.NA, index=working.index, dtype="string")

    def exclude(mask: pd.Series, reason: str) -> None:
        reasons.loc[reasons.isna() & mask.fillna(False)] = reason

    exclude(start_local.isna() | end_local.isna(), "invalid_timestamp")
    if enforce_may_2026:
        window_start = pd.Timestamp("2026-05-01", tz=config.timezone)
        window_end = pd.Timestamp("2026-06-01", tz=config.timezone)
        exclude((start_local < window_start) | (start_local >= window_end), "outside_observation_window")
    exclude(coordinates.isna().any(axis=1), "missing_coordinates")
    south, west, north, east = config.bounds
    exclude(
        ~coordinates["start_lat"].between(south, north)
        | ~coordinates["end_lat"].between(south, north)
        | ~coordinates["start_lng"].between(west, east)
        | ~coordinates["end_lng"].between(west, east),
        "coordinates_outside_city",
    )
    exclude(durations.isna() | (durations <= 0), "invalid_duration")
    exclude(working["ride_id"].astype("string").duplicated(keep=False), "duplicate_trip_id")

    excluded = working.loc[reasons.notna()].copy()
    excluded["exclusion_reason"] = reasons.loc[reasons.notna()]
    valid_index = reasons.loc[reasons.isna()].index
    valid = working.loc[valid_index]
    source_properties = valid.reindex(columns=["rideable_type", "member_casual"]).fillna("").astype(str)
    canonical = pd.DataFrame({
        "city": config.city, "dataset_id": config.dataset_id, "snapshot_id": "2026-05", "mode": "cycle_hire",
        "trip_id": valid["ride_id"].astype(str), "origin_location_id": valid["start_station_id"].astype("string"), "destination_location_id": valid["end_station_id"].astype("string"),
        "origin_latitude": coordinates.loc[valid_index, "start_lat"], "origin_longitude": coordinates.loc[valid_index, "start_lng"],
        "destination_latitude": coordinates.loc[valid_index, "end_lat"], "destination_longitude": coordinates.loc[valid_index, "end_lng"],
        "start_timestamp": start_local.loc[valid_index].dt.tz_convert("UTC"), "end_timestamp": end_local.loc[valid_index].dt.tz_convert("UTC"),
        "duration_seconds": durations.loc[valid_index], "source_properties_json": source_properties.apply(lambda row: json.dumps(row.to_dict(), separators=(",", ":")), axis=1),
    })
    canonical = add_h3_cells(add_temporal_features(canonical, timezone=config.timezone), resolution)
    invalid_h3 = ~canonical["origin_h3"].map(is_valid_cell) | ~canonical["destination_h3"].map(is_valid_cell)
    if invalid_h3.any():
        h3_excluded = valid.loc[canonical.index[invalid_h3]].copy()
        h3_excluded["exclusion_reason"] = "invalid_h3_assignment"
        excluded = pd.concat([excluded, h3_excluded], ignore_index=True)
        canonical = canonical.loc[~invalid_h3]
    return canonical.reset_index(drop=True), excluded.reset_index(drop=True)
