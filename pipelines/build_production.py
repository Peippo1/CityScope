import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pipelines.core.aggregates import activity_aggregate
from pipelines.sources.tfl.acquire import BIKEPOINT_URL, JOURNEY_URLS, bikepoint_path, journey_paths
from pipelines.sources.tfl.transform import to_canonical

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "tfl" / "may-2026"
OUTPUT = ROOT / "data" / "generated"
METADATA_PATH = ROOT / "data" / "metadata" / "london-cycling-production.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> dict:
    paths = [RAW_ROOT / path.name for path in journey_paths(RAW_ROOT)]
    station_path = bikepoint_path(RAW_ROOT)
    missing = [str(path) for path in [*paths, station_path] if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing TfL raw files: {missing}")

    journeys, quarantined = to_canonical(paths, station_path)
    activity = activity_aggregate(journeys)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "quarantine").mkdir(parents=True, exist_ok=True)
    journeys_path = OUTPUT / "london_cycling_production_journeys.parquet"
    activity_path = OUTPUT / "london_cycling_activity.parquet"
    quarantine_path = ROOT / "data" / "quarantine" / "london-tfl-may-2026-unmatched-stations.parquet"
    journeys.to_parquet(journeys_path, index=False)
    activity.to_parquet(activity_path, index=False)
    quarantined.to_parquet(quarantine_path, index=False)

    source_files = []
    for path, url in zip(paths, JOURNEY_URLS):
        source_files.append({"file": path.name, "url": url, "sha256": sha256(path)})
    source_files.append({"file": station_path.name, "url": BIKEPOINT_URL, "sha256": sha256(station_path)})
    metadata = {
        "city": "london",
        "dataset_id": "tfl-santander-cycle-hire",
        "snapshot_id": "2026-05",
        "dataset_name": "TfL Santander Cycles journey data",
        "source_organisation": "Transport for London",
        "source_url": "https://tfl.gov.uk/info-for/open-data-users/our-open-data",
        "source_files": source_files,
        "retrieval_date": datetime.now(timezone.utc).date().isoformat(),
        "observation_start": "2026-05-01T00:00:00Z",
        "observation_end_exclusive": "2026-06-01T00:00:00Z",
        "observation_period": "2026-05-01/2026-05-31",
        "licence_terms_reference": "https://tfl.gov.uk/info-for/open-data-users/our-open-data",
        "attribution_text": "Data provided by Transport for London",
        "source_row_count": int(len(journeys) + len(quarantined)),
        "accepted_row_count": int(len(journeys)),
        "rejected_quarantined_row_count": int(len(quarantined)),
        "quarantine_file": quarantine_path.name,
        "transformation_version": "cityscope-core-v2-tfl-v1",
        "h3_resolution": 9,
        "generated_artifacts": {"journeys": journeys_path.name, "activity": activity_path.name},
        "generated_artifact_version": sha256(activity_path),
        "historical_snapshot": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps({key: result[key] for key in ("source_row_count", "accepted_row_count", "rejected_quarantined_row_count", "generated_artifact_version")}, indent=2))
