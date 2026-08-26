from __future__ import annotations

import pandas as pd

from pipelines.sources.lyft_trip_history import SourceConfig, transform_trip_history


CONFIG = SourceConfig("chicago", "divvy-trips", "America/Chicago", (41.64, -87.95, 42.08, -87.52))


def to_canonical(source: pd.DataFrame, resolution: int = 9) -> pd.DataFrame:
    return transform_trip_history(source, CONFIG, enforce_may_2026=False, resolution=resolution)[0]


def to_validated_canonical(source: pd.DataFrame, resolution: int = 9) -> tuple[pd.DataFrame, pd.DataFrame]:
    return transform_trip_history(source, CONFIG, enforce_may_2026=True, resolution=resolution)
