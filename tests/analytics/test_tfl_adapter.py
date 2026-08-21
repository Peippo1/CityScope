from pathlib import Path

import pandas as pd
import pytest
from h3 import is_valid_cell

from pipelines.sources.tfl.schema import parse_duration_seconds, read_journey_files
from pipelines.sources.tfl.station import enrich_station_coordinates, load_station_reference
from pipelines.sources.tfl.transform import to_canonical


RAW = Path("data/raw/tfl/may-2026")


def test_tfl_schema_and_duration_parser():
    frame = read_journey_files([RAW / "443JourneyDataExtract01May2026-16May2026.csv"])
    assert {"Number", "Start date", "End date", "Start station number", "End station number"}.issubset(frame.columns)
    assert parse_duration_seconds("1h 2m 3s") == 3723
    with pytest.raises(ValueError):
        parse_duration_seconds("0s")


def test_station_enrichment_reports_unmatched_ids():
    stations = pd.DataFrame([{
        "source_location_id": "000001",
        "location_name": "Known",
        "latitude": 51.5,
        "longitude": -0.1,
    }])
    journeys = pd.DataFrame([{
        "origin_location_id": "000001",
        "destination_location_id": "999999",
    }])
    accepted, quarantined = enrich_station_coordinates(journeys, stations)
    assert accepted.empty
    assert len(quarantined) == 1


@pytest.mark.skipif(not (RAW / "bikepoint.json").exists(), reason="production raw data not acquired")
def test_tfl_records_reconcile_through_canonical_and_h3():
    canonical, quarantined = to_canonical(
        [RAW / "443JourneyDataExtract01May2026-16May2026.csv", RAW / "444JourneyDataExtract17May2026-31May2026.csv"],
        RAW / "bikepoint.json",
    )
    assert len(canonical) + len(quarantined) == 863017
    assert canonical["origin_h3"].map(is_valid_cell).all()
    assert canonical["destination_h3"].map(is_valid_cell).all()
    assert canonical["duration_seconds"].gt(0).all()
