from pathlib import Path

RAW_ROOT = Path("data/raw/tfl/may-2026")
JOURNEY_FILES = (
    "443JourneyDataExtract01May2026-16May2026.csv",
    "444JourneyDataExtract17May2026-31May2026.csv",
)
BIKEPOINT_FILE = "bikepoint.json"
JOURNEY_URLS = tuple(
    f"https://s3-eu-west-1.amazonaws.com/cycling.data.tfl.gov.uk/usage-stats/{name}"
    for name in JOURNEY_FILES
)
BIKEPOINT_URL = "https://api.tfl.gov.uk/BikePoint"


def journey_paths(raw_root: Path = RAW_ROOT) -> list[Path]:
    return [raw_root / name for name in JOURNEY_FILES]


def bikepoint_path(raw_root: Path = RAW_ROOT) -> Path:
    return raw_root / BIKEPOINT_FILE
