import pandas as pd
import pytest
import zipfile

from pipelines.multicity import build_production
from pipelines.sources.capital_bikeshare.transform import to_validated_canonical as capital_to_validated
from pipelines.sources.citibike.transform import to_validated_canonical as citibike_to_validated
from pipelines.sources.divvy.transform import to_validated_canonical as divvy_to_validated


BASE_ROW = {
    "ride_id": "ride-1",
    "rideable_type": "classic_bike",
    "started_at": "2026-05-01 00:30:00",
    "ended_at": "2026-05-01 00:45:00",
    "start_station_id": "station-1",
    "end_station_id": "station-2",
    "start_lat": 40.72,
    "start_lng": -74.00,
    "end_lat": 40.73,
    "end_lng": -73.99,
    "member_casual": "member",
}


@pytest.mark.parametrize(
    ("adapter", "coordinates", "expected_utc"),
    [
        (citibike_to_validated, (40.72, -74.00, 40.73, -73.99), "2026-05-01 04:30:00+00:00"),
        (divvy_to_validated, (41.88, -87.63, 41.89, -87.62), "2026-05-01 05:30:00+00:00"),
        (capital_to_validated, (38.90, -77.04, 38.91, -77.03), "2026-05-01 04:30:00+00:00"),
    ],
)
def test_production_adapters_interpret_source_timestamps_in_city_local_time(adapter, coordinates, expected_utc):
    row = {**BASE_ROW, "start_lat": coordinates[0], "start_lng": coordinates[1], "end_lat": coordinates[2], "end_lng": coordinates[3]}

    accepted, excluded = adapter(pd.DataFrame([row]))

    assert excluded.empty
    assert str(accepted.iloc[0]["start_timestamp"]) == expected_utc
    assert accepted.iloc[0]["hour"] == 0
    assert accepted.iloc[0]["snapshot_id"] == "2026-05"


def test_production_adapter_records_each_exclusion_reason_before_h3_assignment():
    rows = [BASE_ROW]
    rows.append({**BASE_ROW, "ride_id": "outside", "started_at": "2026-06-01 00:00:00", "ended_at": "2026-06-01 00:10:00"})
    rows.append({**BASE_ROW, "ride_id": "missing-coordinates", "start_lat": None})
    rows.append({**BASE_ROW, "ride_id": "invalid-duration", "ended_at": "2026-05-01 00:20:00"})
    rows.append({**BASE_ROW, "ride_id": "outside-bounds", "start_lat": 0.0, "start_lng": 0.0})
    rows.extend([{**BASE_ROW, "ride_id": "duplicate"}, {**BASE_ROW, "ride_id": "duplicate"}])

    accepted, excluded = citibike_to_validated(pd.DataFrame(rows))

    assert accepted["trip_id"].tolist() == ["ride-1"]
    assert excluded["exclusion_reason"].value_counts().to_dict() == {
        "duplicate_trip_id": 2,
        "outside_observation_window": 1,
        "missing_coordinates": 1,
        "invalid_duration": 1,
        "coordinates_outside_city": 1,
    }


def test_production_adapter_rejects_schema_drift():
    with pytest.raises(ValueError, match="missing columns"):
        divvy_to_validated(pd.DataFrame([{"ride_id": "incomplete"}]))


def test_dockless_trip_is_retained_without_creating_a_fake_station():
    row = {**BASE_ROW, "start_station_id": None}

    accepted, excluded = citibike_to_validated(pd.DataFrame([row]))

    assert excluded.empty
    assert pd.isna(accepted.iloc[0]["origin_location_id"])


def test_production_builder_streams_zip_and_records_checksums(tmp_path, monkeypatch):
    row = {**BASE_ROW, "start_lat": 41.88, "start_lng": -87.63, "end_lat": 41.89, "end_lng": -87.62}
    csv_path = tmp_path / "trips.csv"
    pd.DataFrame([row, {**row, "ride_id": "ride-2"}]).to_csv(csv_path, index=False)
    archive_path = tmp_path / "202605-divvy-tripdata.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(csv_path, arcname="202605-divvy-tripdata.csv")
    monkeypatch.setattr(build_production, "ROOT", tmp_path)
    monkeypatch.setattr(build_production, "CHUNK_SIZE", 1)

    metadata = build_production.build("chicago", archive_path)

    assert metadata["reconciliation"] == {"source_rows": 2, "accepted_rows": 2, "rejected_rows": 0, "exclusions_by_reason": {}}
    assert metadata["generated_artifact_version"]
    assert (tmp_path / "data/generated/chicago_cycling_production_journeys.parquet").exists()
