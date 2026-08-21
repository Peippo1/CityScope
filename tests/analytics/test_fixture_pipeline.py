from pathlib import Path

from h3 import is_valid_cell

from pipelines.london_cycling.transform import build_activity_aggregate, read_and_transform


def test_fixture_pipeline_creates_deterministic_h3_activity():
    source = Path("pipelines/london_cycling/fixtures/journeys.csv")
    journeys = read_and_transform(source)
    activity = build_activity_aggregate(journeys)

    assert len(journeys) == 5
    assert journeys["is_weekend"].tolist() == [True, True, True, False, False]
    assert journeys["origin_h3"].map(is_valid_cell).all()
    assert journeys["destination_h3"].map(is_valid_cell).all()
    assert int(activity["total_journeys"].sum()) == 10
    assert int(activity["origin_journeys"].sum()) == 5
    assert int(activity["destination_journeys"].sum()) == 5
