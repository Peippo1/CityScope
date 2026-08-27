import json

import pytest

from apps.api.app.artifacts import HISTORICAL_COHORT
from scripts.check_cohort_sources import validate_manifests


def _write_manifest(root, city, snapshot="2026-05"):
    metadata = root / "data" / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / f"{city}-cycling-production.json").write_text(json.dumps({
        "snapshot_id": snapshot,
        "source_files": [{"url": f"https://example.test/{city}.zip", "sha256": "a" * 64}],
    }))


def test_cohort_source_monitor_requires_one_matched_snapshot(tmp_path):
    for city in HISTORICAL_COHORT:
        _write_manifest(tmp_path, city, "2026-04" if city == "chicago" else "2026-05")

    with pytest.raises(ValueError, match="one snapshot"):
        validate_manifests(tmp_path)


def test_cohort_source_monitor_returns_pinned_provenance(tmp_path):
    for city in HISTORICAL_COHORT:
        _write_manifest(tmp_path, city)

    result = validate_manifests(tmp_path)

    assert result["snapshot_id"] == "2026-05"
    assert len(result["sources"]) == 4
