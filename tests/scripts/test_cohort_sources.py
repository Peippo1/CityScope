import json
from io import BytesIO

import pytest
from urllib.error import HTTPError

from apps.api.app.artifacts import HISTORICAL_COHORT
from scripts import check_cohort_sources
from scripts.check_cohort_sources import probe, probe_sources, validate_manifests


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


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def test_probe_falls_back_to_bounded_get_when_head_returns_404(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        if request.get_method() == "HEAD":
            raise HTTPError(request.full_url, 404, "not supported", {}, BytesIO())
        return _Response()

    monkeypatch.setattr(check_cohort_sources, "urlopen", fake_urlopen)

    assert probe("https://example.test/status") == 200
    assert [request.get_method() for request in requests] == ["HEAD", "GET"]
    assert requests[1].get_header("Range") == "bytes=0-0"


def test_probe_sources_reports_every_failure(monkeypatch):
    def fake_probe(url):
        if "chicago" in url:
            raise HTTPError(url, 404, "missing", {}, BytesIO())
        return 200

    monkeypatch.setattr(check_cohort_sources, "probe", fake_probe)
    sources = [
        {"city": "london", "url": "https://example.test/london", "sha256": "a" * 64},
        {"city": "chicago", "url": "https://example.test/chicago", "sha256": "b" * 64},
        {"city": "new_york", "url": "https://example.test/new-york", "sha256": "c" * 64},
    ]

    results, healthy = probe_sources(sources)

    assert not healthy
    assert len(results) == 3
    assert results[1]["error"].startswith("HTTPError:")
    assert results[2]["status"] == 200
