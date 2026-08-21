import pandas as pd

from pipelines.core.spatial import add_h3_cells
from pipelines.core.temporal import add_temporal_features
from .schema import parse_duration_or_none, read_journey_files
from .station import enrich_station_coordinates


def to_canonical(paths, station_path, resolution: int = 9):
    source = read_journey_files(paths)
    durations = source["Total duration"].map(parse_duration_or_none)
    valid_duration = durations.notna()
    journeys = pd.DataFrame({
        "city": "london",
        "dataset_id": "tfl-santander-cycle-hire",
        "snapshot_id": "2026-05",
        "mode": "cycle_hire",
        "trip_id": source["Number"].astype(str),
        "origin_location_id": source["Start station number"].astype(str).str.zfill(6),
        "destination_location_id": source["End station number"].astype(str).str.zfill(6),
        "start_timestamp": pd.to_datetime(source["Start date"], utc=True),
        "end_timestamp": pd.to_datetime(source["End date"], utc=True),
        "duration_seconds": durations,
        "source_properties_json": source[["Bike model", "Bike number", "Start station", "End station"]].to_json(orient="records"),
    })
    journeys["source_properties_json"] = source[["Bike model", "Bike number", "Start station", "End station"]].apply(
        lambda row: row.to_json(), axis=1
    )
    stations = __import__("pipelines.sources.tfl.station", fromlist=["load_station_reference"]).load_station_reference(station_path)
    invalid_duration = journeys.loc[~valid_duration].copy()
    enriched, unmatched_stations = enrich_station_coordinates(journeys.loc[valid_duration].copy(), stations)
    quarantined = pd.concat([invalid_duration, unmatched_stations], ignore_index=True)
    enriched = add_temporal_features(enriched)
    enriched = add_h3_cells(enriched, resolution)
    return enriched, quarantined
