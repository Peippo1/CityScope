from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipelines.core.spatial import add_h3_cells
from pipelines.core.temporal import add_temporal_features


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "generated"
METADATA = ROOT / "data" / "metadata"

CITY_FIXTURES = {
    "new_york": {"name": "Citi Bike trip history", "organisation": "Citi Bike", "url": "https://citibikenyc.com/system-data", "attribution": "Data provided by Citi Bike", "points": [(40.7580, -73.9855), (40.7306, -73.9866), (40.7484, -73.9857)]},
    "chicago": {"name": "Divvy Trips", "organisation": "City of Chicago", "url": "https://data.cityofchicago.org/d/fg6s-gzvg", "attribution": "Data provided by the City of Chicago", "points": [(41.8781, -87.6298), (41.8925, -87.6260), (41.8676, -87.6167)]},
    "washington_dc": {"name": "Capital Bikeshare trip history", "organisation": "Capital Bikeshare", "url": "https://capitalbikeshare.com/system-data", "attribution": "Data provided by Capital Bikeshare", "points": [(38.9072, -77.0369), (38.8987, -77.0230), (38.9145, -77.0219)]},
}


def _journeys(city: str, points: list[tuple[float, float]]) -> pd.DataFrame:
    rows = []
    for index in range(12):
        origin = points[index % len(points)]
        destination = points[(index + 1) % len(points)]
        start = pd.Timestamp("2026-05-03T07:00:00Z") + pd.Timedelta(index * 6, unit="h")
        rows.append({
            "city": city, "dataset_id": f"{city}-fixture", "snapshot_id": "2026-05-fixture", "mode": "cycle_hire",
            "trip_id": f"{city}-{index}", "origin_location_id": f"{city}-origin-{index % len(points)}", "destination_location_id": f"{city}-destination-{(index + 1) % len(points)}",
            "origin_latitude": origin[0], "origin_longitude": origin[1], "destination_latitude": destination[0], "destination_longitude": destination[1],
            "start_timestamp": start, "end_timestamp": start + pd.Timedelta(12 + index, unit="m"), "duration_seconds": 720 + index * 60, "source_properties_json": "{}",
        })
    return add_h3_cells(add_temporal_features(pd.DataFrame(rows)), 9)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    METADATA.mkdir(parents=True, exist_ok=True)
    for city, details in CITY_FIXTURES.items():
        journeys = _journeys(city, details["points"])
        journeys.to_parquet(OUTPUT / f"{city}_cycling_fixture_journeys.parquet", index=False)
        metadata = {
            "city": city, "dataset_id": f"{city}-fixture", "dataset_name": details["name"], "snapshot_id": "2026-05-fixture",
            "source_organisation": details["organisation"], "source_url": details["url"], "observation_start": "2026-05-01T00:00:00Z", "observation_end_exclusive": "2026-06-01T00:00:00Z",
            "observation_period": "2026-05-01/2026-05-31", "historical_snapshot": True, "h3_resolution": 9,
            "attribution_text": details["attribution"], "licence_terms_reference": "Fixture only; production source terms apply.", "source_files": [],
        }
        (METADATA / f"{city}-cycling-fixture.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
