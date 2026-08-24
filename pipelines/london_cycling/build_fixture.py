import json
from pathlib import Path

from .transform import build_activity_aggregate, read_and_transform

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).parent / "fixtures" / "journeys.csv"
OUTPUT = ROOT / "data" / "generated"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    journeys = read_and_transform(SOURCE)
    activity = build_activity_aggregate(journeys)
    # The fixture input keeps its original vertical-slice name, while the
    # generated artifact conforms to the shared canonical analytics contract.
    journeys.rename(columns={"journey_id": "trip_id"}).to_parquet(
        OUTPUT / "london_cycling_journeys.parquet", index=False
    )
    # Keep fixtures isolated so test setup can never overwrite the deployable
    # production activity artifact or invalidate its provenance checksum.
    activity.to_parquet(OUTPUT / "london_cycling_fixture_activity.parquet", index=False)
    metadata = {
        "city": "london",
        "dataset": "london-cycling-fixture",
        "observation_period": "2024-01-06/2024-01-08",
        "source": "synthetic fixture shaped from the licensed London cycling schema",
        "primary_h3_resolution": 9,
        "journey_count": len(journeys),
    }
    (ROOT / "data" / "metadata").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "metadata" / "london-cycling-fixture.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
