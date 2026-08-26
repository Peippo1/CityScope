"""Build validated May 2026 production artifacts from official downloaded CSV files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from pipelines.sources.capital_bikeshare.transform import to_canonical as capital_to_canonical
from pipelines.sources.citibike.transform import to_canonical as citibike_to_canonical
from pipelines.sources.divvy.transform import to_canonical as divvy_to_canonical


ROOT = Path(__file__).resolve().parents[2]
TRANSFORMS = {"new_york": citibike_to_canonical, "chicago": divvy_to_canonical, "washington_dc": capital_to_canonical}
SOURCES = {"new_york": ("Citi Bike", "https://citibikenyc.com/system-data", "NYCBS Data Use Policy"), "chicago": ("City of Chicago", "https://data.cityofchicago.org/d/fg6s-gzvg", "City of Chicago Data Portal terms"), "washington_dc": ("Capital Bikeshare", "https://capitalbikeshare.com/system-data", "Capital Bikeshare Data License Agreement")}


def build(city: str, source: Path) -> dict:
    if city not in TRANSFORMS: raise ValueError(f"Unsupported production city: {city}")
    raw = pd.read_csv(source)
    canonical = TRANSFORMS[city](raw)
    before = len(canonical)
    canonical = canonical.dropna(subset=["origin_latitude", "origin_longitude", "destination_latitude", "destination_longitude"])
    canonical = canonical[(canonical["duration_seconds"] > 0) & ~canonical["trip_id"].duplicated()]
    canonical = canonical[(canonical["start_timestamp"] >= "2026-05-01T00:00:00Z") & (canonical["start_timestamp"] < "2026-06-01T00:00:00Z")]
    output = ROOT / "data" / "generated"; metadata_dir = ROOT / "data" / "metadata"; output.mkdir(parents=True, exist_ok=True); metadata_dir.mkdir(parents=True, exist_ok=True)
    artifact = output / f"{city}_cycling_production_journeys.parquet"; canonical.to_parquet(artifact, index=False)
    organisation, source_url, licence = SOURCES[city]
    metadata = {"city": city, "dataset_id": canonical["dataset_id"].iloc[0], "dataset_name": f"{organisation} May 2026 trip history", "snapshot_id": "2026-05", "source_organisation": organisation, "source_url": source_url, "observation_start": "2026-05-01T00:00:00Z", "observation_end_exclusive": "2026-06-01T00:00:00Z", "observation_period": "2026-05-01/2026-05-31", "historical_snapshot": True, "h3_resolution": 9, "attribution_text": f"Data provided by {organisation}", "licence_terms_reference": licence, "source_files": [{"file": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}], "reconciliation": {"source_rows": len(raw), "accepted_rows": len(canonical), "rejected_rows": before - len(canonical)}}
    (metadata_dir / f"{city}-cycling-production.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata
