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
