from pathlib import Path

import pandas as pd
from h3 import is_valid_cell

from pipelines.core.aggregates import activity_aggregate
from pipelines.sources.citibike.transform import to_canonical


def test_citibike_fixture_uses_shared_canonical_pipeline():
    source = pd.read_csv(Path("pipelines/sources/citibike/fixtures/trips.csv"))
    canonical = to_canonical(source)
    aggregate = activity_aggregate(canonical)

    assert set(canonical["city"]) == {"new_york"}
    assert canonical["origin_h3"].map(is_valid_cell).all()
    assert canonical["destination_h3"].map(is_valid_cell).all()
    assert len(canonical) == 2
    assert int(aggregate["total_journeys"].sum()) == 4
