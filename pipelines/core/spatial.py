import pandas as pd
from h3 import latlng_to_cell


def add_h3_cells(
    frame: pd.DataFrame,
    resolution: int,
    origin_latitude: str = "origin_latitude",
    origin_longitude: str = "origin_longitude",
    destination_latitude: str = "destination_latitude",
    destination_longitude: str = "destination_longitude",
) -> pd.DataFrame:
    result = frame.copy()
    result["origin_h3"] = [
        latlng_to_cell(lat, lon, resolution)
        for lat, lon in zip(result[origin_latitude], result[origin_longitude])
    ]
    result["destination_h3"] = [
        latlng_to_cell(lat, lon, resolution)
        for lat, lon in zip(result[destination_latitude], result[destination_longitude])
    ]
    return result
