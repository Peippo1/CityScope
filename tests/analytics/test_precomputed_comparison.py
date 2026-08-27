import json
from pathlib import Path

import pandas as pd

from apps.api.app.analytics.mobility import MobilityAnalytics
from pipelines.multicity.build_comparison import build_comparison_artifact


CITIES = ("london", "new_york", "chicago", "washington_dc")


def _write_city(root: Path, city: str, version: str = "sha-1") -> None:
    generated = root / "data" / "generated"
    metadata = root / "data" / "metadata"
    generated.mkdir(parents=True, exist_ok=True)
    metadata.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "trip_id": f"{city}-{index}",
            "origin_location_id": "A",
            "destination_location_id": "B",
            "origin_h3": "89194ad3353ffff",
            "destination_h3": "89194ad3357ffff",
            "duration_seconds": 600 + index * 60,
            "hour": 8 if index == 0 else 12,
            "is_weekend": index == 1,
        }
        for index in range(2)
    ]
    pd.DataFrame(rows).to_parquet(generated / f"{city}_cycling_production_journeys.parquet", index=False)
    (metadata / f"{city}-cycling-production.json").write_text(json.dumps({
        "city": city,
        "snapshot_id": "2026-05",
        "generated_artifact_version": version,
    }))


def test_precomputed_comparison_is_used_when_source_fingerprints_match(tmp_path, monkeypatch):
    for city in CITIES:
        _write_city(tmp_path, city)
    artifact = build_comparison_artifact(tmp_path)
    analytics = MobilityAnalytics(tmp_path)
    monkeypatch.setattr(analytics, "_uncached_comparison_value", lambda *_: (_ for _ in ()).throw(AssertionError("Parquet fallback should not run")))

    result = analytics.compare_cities(list(CITIES), "weekend_share")

    assert artifact == tmp_path / "data" / "generated" / "cross_city_comparison.json"
    assert [row["value"] for row in result["cities"]] == [0.5, 0.5, 0.5, 0.5]


def test_stale_precomputed_comparison_falls_back_to_parquet(tmp_path, monkeypatch):
    for city in CITIES:
        _write_city(tmp_path, city)
    build_comparison_artifact(tmp_path)
    _write_city(tmp_path, "london", version="sha-2")
    analytics = MobilityAnalytics(tmp_path)
    monkeypatch.setattr(analytics, "_uncached_comparison_value", lambda city, metric: 0.25 if city == "london" else 0.5)

    result = analytics.compare_cities(list(CITIES), "weekend_share")

    london = next(row for row in result["cities"] if row["city"] == "london")
    assert london["value"] == 0.25
