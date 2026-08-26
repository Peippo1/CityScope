from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipelines.london_cycling.transform import build_activity_aggregate, read_and_transform
from apps.api.app.analytics.duckdb_reader import ActivityReader


def test_duckdb_reader_returns_ranked_activity(tmp_path: Path):
    journeys = read_and_transform(Path("pipelines/london_cycling/fixtures/journeys.csv"))
    activity = build_activity_aggregate(journeys)
    parquet = tmp_path / "activity.parquet"
    activity.to_parquet(parquet, index=False)

    result = ActivityReader(parquet).activity(limit=1)

    assert len(result) == 1
    assert result[0]["total_journeys"] == int(activity.iloc[0]["total_journeys"])


def test_duckdb_reader_handles_concurrent_requests(tmp_path: Path):
    journeys = read_and_transform(Path("pipelines/london_cycling/fixtures/journeys.csv"))
    activity = build_activity_aggregate(journeys)
    parquet = tmp_path / "activity.parquet"
    activity.to_parquet(parquet, index=False)
    reader = ActivityReader(parquet)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: reader.activity(limit=2), range(32)))

    assert all(len(result) == 2 for result in results)
    assert {result[0]["h3_cell"] for result in results} == {results[0][0]["h3_cell"]}
