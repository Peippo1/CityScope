import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


def load_station_reference(path: Path) -> pd.DataFrame:
    points = json.loads(path.read_text())
    rows = []
    for point in points:
        terminal_name = next(
            (item.get("value") for item in point.get("additionalProperties", []) if item.get("key") == "TerminalName"),
            None,
        )
        if not terminal_name:
            continue
        rows.append({
            "source_location_id": str(terminal_name).zfill(6),
            "location_name": point.get("commonName", ""),
            "latitude": point.get("lat"),
            "longitude": point.get("lon"),
        })
    return pd.DataFrame(rows).drop_duplicates("source_location_id")


def enrich_station_coordinates(journeys: pd.DataFrame, stations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    lookup = stations.set_index("source_location_id")
    result = journeys.copy()
    for prefix in ("origin", "destination"):
        ids = result[f"{prefix}_location_id"].astype(str).str.zfill(6)
        result[f"{prefix}_latitude"] = ids.map(lookup["latitude"])
        result[f"{prefix}_longitude"] = ids.map(lookup["longitude"])
    valid = result[["origin_latitude", "origin_longitude", "destination_latitude", "destination_longitude"]].notna().all(axis=1)
    quarantined = result.loc[~valid].copy()
    return result.loc[valid].reset_index(drop=True), quarantined.reset_index(drop=True)


def normalize_station_name(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", ascii_value)
