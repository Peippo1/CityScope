"""Build validated May 2026 production artifacts from official CSV or ZIP files."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pipelines.sources.capital_bikeshare.transform import to_validated_canonical as capital_to_canonical
from pipelines.sources.citibike.transform import to_validated_canonical as citibike_to_canonical
from pipelines.sources.divvy.transform import to_validated_canonical as divvy_to_canonical


ROOT = Path(__file__).resolve().parents[2]
CHUNK_SIZE = 250_000
CSV_DTYPES = {"ride_id": "string", "start_station_id": "string", "end_station_id": "string", "rideable_type": "string", "member_casual": "string"}
TRANSFORMS = {"new_york": citibike_to_canonical, "chicago": divvy_to_canonical, "washington_dc": capital_to_canonical}
SOURCES = {
    "new_york": {"organisation": "Citi Bike", "page": "https://citibikenyc.com/system-data", "archive": "https://s3.amazonaws.com/tripdata/202605-citibike-tripdata.zip", "licence": "NYCBS Data Use Policy", "timezone": "America/New_York"},
    "chicago": {"organisation": "Divvy", "page": "https://divvybikes.com/system-data", "archive": "https://divvy-tripdata.s3.amazonaws.com/202605-divvy-tripdata.zip", "licence": "Divvy Data License Agreement", "timezone": "America/Chicago"},
    "washington_dc": {"organisation": "Capital Bikeshare", "page": "https://capitalbikeshare.com/system-data", "archive": "https://s3.amazonaws.com/capitalbikeshare-data/202605-capitalbikeshare-tripdata.zip", "licence": "Capital Bikeshare Data License Agreement", "timezone": "America/New_York"},
}
DATASET_IDS = {"new_york": "citibike-trip-history", "chicago": "divvy-trips", "washington_dc": "capital-bikeshare-trip-history"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_chunks(source: Path) -> Iterator[pd.DataFrame]:
    if source.suffix.lower() != ".zip":
        yield from pd.read_csv(source, chunksize=CHUNK_SIZE, dtype=CSV_DTYPES)
        return
    with zipfile.ZipFile(source) as archive:
        members = sorted(name for name in archive.namelist() if name.lower().endswith(".csv") and not name.startswith("__MACOSX/"))
        if not members:
            raise ValueError(f"ZIP archive contains no CSV files: {source}")
        for member in members:
            with archive.open(member) as stream:
                yield from pd.read_csv(stream, chunksize=CHUNK_SIZE, dtype=CSV_DTYPES)


def _write_chunk(writer: pq.ParquetWriter | None, frame: pd.DataFrame, path: Path) -> pq.ParquetWriter | None:
    if frame.empty:
        return writer
    table = pa.Table.from_pandas(frame, preserve_index=False)
    if writer is None:
        writer = pq.ParquetWriter(path, table.schema, compression="zstd")
    writer.write_table(table)
    return writer


def build(city: str, source: Path) -> dict:
    if city not in TRANSFORMS:
        raise ValueError(f"Unsupported production city: {city}")
    if not source.exists():
        raise FileNotFoundError(source)

    output = ROOT / "data" / "generated"
    metadata_dir = ROOT / "data" / "metadata"
    quarantine_dir = ROOT / "data" / "quarantine"
    output.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    artifact = output / f"{city}_cycling_production_journeys.parquet"
    quarantine = quarantine_dir / f"{city}-cycling-production-exclusions.parquet"
    artifact.unlink(missing_ok=True)
    quarantine.unlink(missing_ok=True)

    accepted_writer: pq.ParquetWriter | None = None
    excluded_writer: pq.ParquetWriter | None = None
    source_rows = accepted_rows = 0
    exclusions: Counter[str] = Counter()
    seen_trip_ids: set[str] = set()
    try:
        for raw in source_chunks(source):
            source_rows += len(raw)
            trip_ids = raw["ride_id"].astype(str)
            repeated_from_prior_chunk = trip_ids.isin(seen_trip_ids)
            accepted, excluded = TRANSFORMS[city](raw.loc[~repeated_from_prior_chunk])
            if repeated_from_prior_chunk.any():
                repeated = raw.loc[repeated_from_prior_chunk].copy()
                repeated["exclusion_reason"] = "duplicate_trip_id"
                excluded = pd.concat([excluded, repeated], ignore_index=True)
            seen_trip_ids.update(trip_ids)
            accepted_rows += len(accepted)
            exclusions.update(excluded["exclusion_reason"].value_counts().to_dict())
            accepted_writer = _write_chunk(accepted_writer, accepted, artifact)
            excluded_writer = _write_chunk(excluded_writer, excluded.astype("string"), quarantine)
    finally:
        if accepted_writer:
            accepted_writer.close()
        if excluded_writer:
            excluded_writer.close()
    if accepted_rows == 0 or not artifact.exists():
        raise ValueError(f"{city} production build accepted no rows")

    details = SOURCES[city]
    local_start = pd.Timestamp("2026-05-01", tz=details["timezone"])
    local_end = pd.Timestamp("2026-06-01", tz=details["timezone"])
    rejected_rows = source_rows - accepted_rows
    if rejected_rows != sum(exclusions.values()):
        raise ValueError("Production reconciliation failed")
    metadata = {
        "city": city,
        "dataset_id": DATASET_IDS[city],
        "dataset_name": f"{details['organisation']} May 2026 trip history",
        "snapshot_id": "2026-05",
        "source_organisation": details["organisation"],
        "source_url": details["page"],
        "observation_start": local_start.tz_convert("UTC").isoformat(),
        "observation_end_exclusive": local_end.tz_convert("UTC").isoformat(),
        "observation_period": "2026-05-01/2026-05-31",
        "observation_timezone": details["timezone"],
        "historical_snapshot": True,
        "h3_resolution": 9,
        "attribution_text": f"Data provided by {details['organisation']}",
        "licence_terms_reference": details["licence"],
        "source_files": [{"file": source.name, "url": details["archive"], "sha256": sha256(source)}],
        "reconciliation": {"source_rows": source_rows, "accepted_rows": accepted_rows, "rejected_rows": rejected_rows, "exclusions_by_reason": dict(sorted(exclusions.items()))},
        "quarantine_file": quarantine.name if quarantine.exists() else None,
        "transformation_version": "cityscope-core-v3-lyft-trip-history-v1",
        "generated_artifacts": {"journeys": artifact.name},
        "generated_artifact_version": sha256(artifact),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (metadata_dir / f"{city}-cycling-production.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("city", choices=sorted(TRANSFORMS))
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    metadata = build(args.city, args.source)
    print(json.dumps(metadata["reconciliation"], indent=2))


if __name__ == "__main__":
    main()
