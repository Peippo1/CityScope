"""Build a validated cross-city metric matrix for low-latency API reads."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from apps.api.app.analytics.mobility import COMPARISON_METRICS, MobilityAnalytics
from apps.api.app.cities import historical_city_ids


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_NAME = "cross_city_comparison.json"


def _source_fingerprint(analytics: MobilityAnalytics, city: str) -> dict[str, str | None]:
    metadata, journeys = analytics._dataset(city)
    return {
        "snapshot_id": metadata.get("snapshot_id"),
        "artifact_version": metadata.get("generated_artifact_version"),
        "artifact_name": journeys.name,
    }


def build_comparison_artifact(root: Path = ROOT) -> Path:
    analytics = MobilityAnalytics(root, use_precomputed=False)
    cities = historical_city_ids()
    payload = {
        "schema_version": 1,
        "observation_period": "2026-05-01/2026-05-31",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_fingerprints": {city: _source_fingerprint(analytics, city) for city in cities},
        "metrics": {
            metric: {city: analytics._uncached_comparison_value(city, metric) for city in cities}
            for metric in sorted(COMPARISON_METRICS)
        },
    }
    output = root / "data" / "generated" / OUTPUT_NAME
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return output


if __name__ == "__main__":
    print(build_comparison_artifact())
