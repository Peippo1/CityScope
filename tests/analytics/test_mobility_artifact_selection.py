import json

import pandas as pd
from h3 import latlng_to_cell

from apps.api.app.analytics.mobility import MobilityAnalytics
from pipelines.core.analytics_contract import TimeFilter


def test_clean_checkout_uses_fixture_when_production_artifact_is_absent(tmp_path):
    metadata = tmp_path / "data" / "metadata"
    generated = tmp_path / "data" / "generated"
    metadata.mkdir(parents=True)
    generated.mkdir(parents=True)
    (metadata / "london-cycling-production.json").write_text(json.dumps({"dataset_id": "production"}))
    (metadata / "london-cycling-fixture.json").write_text(json.dumps({"dataset": "fixture", "primary_h3_resolution": 9}))

    cell = latlng_to_cell(51.5074, -0.1278, 9)
    pd.DataFrame([{
        "trip_id": "fixture-1",
        "start_timestamp": pd.Timestamp("2024-01-06T09:00:00Z"),
        "time_of_day": "morning",
        "origin_h3": cell,
        "destination_h3": cell,
    }]).to_parquet(generated / "london_cycling_journeys.parquet", index=False)

    analytics = MobilityAnalytics(tmp_path)

    assert analytics.metadata_path.name == "london-cycling-fixture.json"
    assert analytics.find_hotspots("london", "total_activity", TimeFilter(), 1)[0]["value"] == 2
