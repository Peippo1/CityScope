import json

import pandas as pd

from pipelines.core.spatial import add_h3_cells
from pipelines.core.temporal import add_temporal_features
from .schema import parse_duration_or_none, read_journey_files
from .station import enrich_station_coordinates


def to_canonical(paths, station_path, resolution: int = 9):
    source = read_journey_files(paths)
    durations = source["Total duration"].map(parse_duration_or_none)
    start_local = pd.to_datetime(source["Start date"], format="mixed", dayfirst=True, errors="coerce").dt.tz_localize("Europe/London", ambiguous="NaT", nonexistent="NaT")
    end_local = pd.to_datetime(source["End date"], format="mixed", dayfirst=True, errors="coerce").dt.tz_localize("Europe/London", ambiguous="NaT", nonexistent="NaT")
    reasons = pd.Series(pd.NA, index=source.index, dtype="string")

    def exclude(mask: pd.Series, reason: str) -> None:
        reasons.loc[reasons.isna() & mask.fillna(False)] = reason

    exclude(start_local.isna() | end_local.isna(), "invalid_timestamp")
    exclude(durations.isna() | (durations <= 0), "invalid_duration")
    exclude((start_local < pd.Timestamp("2026-05-01", tz="Europe/London")) | (start_local >= pd.Timestamp("2026-06-01", tz="Europe/London")), "outside_observation_window")
    exclude(source["Number"].astype("string").duplicated(keep=False), "duplicate_trip_id")
    journeys = pd.DataFrame({
        "city": "london",
        "dataset_id": "tfl-santander-cycle-hire",
        "snapshot_id": "2026-05",
        "mode": "cycle_hire",
        "trip_id": source["Number"].astype(str),
        "origin_location_id": source["Start station number"].astype(str).str.zfill(6),
        "destination_location_id": source["End station number"].astype(str).str.zfill(6),
        "start_timestamp": start_local.dt.tz_convert("UTC"),
        "end_timestamp": end_local.dt.tz_convert("UTC"),
        "duration_seconds": durations,
        "source_properties_json": "{}",
    })
    source_properties = source.reindex(columns=["Bike model", "Bike number", "Start station", "End station"]).fillna("").astype(str)
    journeys["source_properties_json"] = source_properties.apply(lambda row: json.dumps(row.to_dict(), separators=(",", ":")), axis=1)
    stations = __import__("pipelines.sources.tfl.station", fromlist=["load_station_reference"]).load_station_reference(station_path)
    invalid_source = journeys.loc[reasons.notna()].copy()
    invalid_source["exclusion_reason"] = reasons.loc[reasons.notna()]
    enriched, unmatched_stations = enrich_station_coordinates(journeys.loc[reasons.isna()].copy(), stations)
    unmatched_stations["exclusion_reason"] = "missing_station_coordinates"
    quarantined = pd.concat([invalid_source, unmatched_stations], ignore_index=True)
    enriched = add_temporal_features(enriched, timezone="Europe/London")
    enriched = add_h3_cells(enriched, resolution)
    return enriched, quarantined
