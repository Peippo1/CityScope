import json

import pandas as pd

from pipelines.multicity.build_fixture import main as build_multicity_fixture
from apps.api.app.analytics.mobility import MobilityAnalytics


def test_cross_city_comparison_is_normalized_and_uses_matched_window():
    build_multicity_fixture()
    result = MobilityAnalytics(__import__("pathlib").Path(__file__).resolve().parents[2]).compare_cities(
        ["london", "new_york", "chicago", "washington_dc"], "trips_per_active_station_day"
    )

    assert result["observation_period"] == "2026-05-01/2026-05-31"
    assert [row["rank"] for row in result["cities"]] == [1, 2, 3, 4]
    assert any("raw trip totals" in limitation.lower() for limitation in result["limitations"])


def test_cross_city_comparison_rejects_raw_count_metric():
    build_multicity_fixture()
    analytics = MobilityAnalytics(__import__("pathlib").Path(__file__).resolve().parents[2])
    try:
        analytics.compare_cities(["london", "new_york"], "total_activity")
    except ValueError as exc:
        assert "Unsupported cross-city metric" in str(exc)
    else:
        raise AssertionError("raw activity totals must not be comparable")


def test_hotspot_concentration_is_a_share_of_unique_trips():
    build_multicity_fixture()
    result = MobilityAnalytics(__import__("pathlib").Path(__file__).resolve().parents[2]).compare_cities(
        ["london", "new_york", "chicago", "washington_dc"], "hotspot_concentration"
    )

    assert all(0 <= row["value"] <= 1 for row in result["cities"])


def test_station_normalization_supports_original_london_fixture_schema(tmp_path):
    generated = tmp_path / "data" / "generated"
    metadata = tmp_path / "data" / "metadata"
    generated.mkdir(parents=True)
    metadata.mkdir(parents=True)
    pd.DataFrame([
        {"trip_id": "one", "origin_station_id": "A", "destination_station_id": "B"},
        {"trip_id": "two", "origin_station_id": "A", "destination_station_id": "C"},
    ]).to_parquet(generated / "london_cycling_journeys.parquet", index=False)
    (metadata / "london-cycling-fixture.json").write_text(json.dumps({"snapshot_id": "2026-05-fixture"}))

    value = MobilityAnalytics(tmp_path)._uncached_comparison_value("london", "trips_per_active_station_day")

    assert value == round(2 / 3 / 31, 4)


def test_duckdb_spill_directory_is_writable_in_a_non_root_container():
    with MobilityAnalytics._connect() as connection:
        configured = connection.execute("SELECT current_setting('temp_directory')").fetchone()[0]

    assert configured == "/tmp/cityscope-duckdb"
