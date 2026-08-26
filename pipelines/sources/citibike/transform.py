import pandas as pd

from pipelines.sources.lyft_trip_history import SourceConfig, transform_trip_history


CONFIG = SourceConfig("new_york", "citibike-trip-history", "America/New_York", (40.49, -74.30, 40.92, -73.68))


def to_canonical(source: pd.DataFrame, resolution: int = 9) -> pd.DataFrame:
    return transform_trip_history(source, CONFIG, enforce_may_2026=False, resolution=resolution)[0]


def to_validated_canonical(source: pd.DataFrame, resolution: int = 9) -> tuple[pd.DataFrame, pd.DataFrame]:
    return transform_trip_history(source, CONFIG, enforce_may_2026=True, resolution=resolution)
