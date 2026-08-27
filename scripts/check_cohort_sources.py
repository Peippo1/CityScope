"""Validate the pinned cohort manifests and optionally probe every official source URL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.api.app.artifacts import HISTORICAL_COHORT


ROOT = Path(__file__).resolve().parents[1]


def validate_manifests(root: Path = ROOT) -> dict[str, object]:
    snapshots: set[str] = set()
    sources: list[dict[str, str]] = []
    for city in HISTORICAL_COHORT:
        path = root / "data" / "metadata" / f"{city}-cycling-production.json"
        metadata = json.loads(path.read_text())
        snapshot = metadata["snapshot_id"]
        source_files = metadata["source_files"]
        if not isinstance(source_files, list) or not source_files:
            raise ValueError(f"Production manifest has no source files for {city}")
        snapshots.add(snapshot)
        for source in source_files:
            if not source.get("url") or not source.get("sha256"):
                raise ValueError(f"Production source provenance is incomplete for {city}")
            sources.append({"city": city, "url": source["url"], "sha256": source["sha256"]})
    if len(snapshots) != 1:
        raise ValueError("Historical cohort manifests do not share one snapshot")
    return {"status": "valid", "snapshot_id": snapshots.pop(), "sources": sources}


def probe(url: str, timeout_s: float = 20.0) -> int:
    request = Request(url, method="HEAD", headers={"User-Agent": "CityScope-cohort-monitor/1.0"})
    try:
        with urlopen(request, timeout=timeout_s) as response:
            return response.status
    except HTTPError as exc:
        if exc.code not in {403, 405}:
            raise
    request = Request(url, headers={"User-Agent": "CityScope-cohort-monitor/1.0", "Range": "bytes=0-0"})
    with urlopen(request, timeout=timeout_s) as response:
        return response.status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="Make bounded requests to every pinned official source URL")
    args = parser.parse_args()
    result = validate_manifests()
    if args.probe:
        result["probes"] = [{"city": source["city"], "url": source["url"], "status": probe(source["url"])} for source in result["sources"]]  # type: ignore[index]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
