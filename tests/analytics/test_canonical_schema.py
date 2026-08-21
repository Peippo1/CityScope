from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from pipelines.core.models import Coordinate, DatasetSnapshot, MobilityTrip, Provenance


def test_canonical_models_validate_mobility_trip_and_snapshot():
    provenance = Provenance(
        source_organisation="Example",
        source_url="https://example.com/data",
        source_file="trips.csv",
        source_checksum_sha256="a" * 64,
    )
    snapshot = DatasetSnapshot(
        city="london",
        dataset_id="example-bike-share",
        snapshot_id="2026-05",
        mode="cycle_hire",
        observation_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        observation_end=datetime(2026, 6, 1, tzinfo=timezone.utc),
        provenance=[provenance],
        h3_resolution=9,
    )
    trip = MobilityTrip(
        city=snapshot.city,
        dataset_id=snapshot.dataset_id,
        snapshot_id=snapshot.snapshot_id,
        mode=snapshot.mode,
        trip_id="trip-1",
        origin_location_id="origin-1",
        destination_location_id="destination-1",
        origin=Coordinate(latitude=51.5, longitude=-0.1),
        destination=Coordinate(latitude=51.51, longitude=-0.11),
        start_timestamp=snapshot.observation_start,
        end_timestamp=datetime(2026, 5, 1, 0, 10, tzinfo=timezone.utc),
        duration_seconds=600,
        source_properties={"member_type": "member"},
    )
    assert snapshot.city == trip.city
    assert trip.source_properties["member_type"] == "member"


def test_canonical_coordinate_bounds_are_enforced():
    with pytest.raises(ValidationError):
        Coordinate(latitude=91, longitude=0)
