from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "Number", "Start date", "Start station number", "Start station",
    "End date", "End station number", "End station", "Total duration",
}


def read_journey_files(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = pd.read_csv(path)
        missing = REQUIRED_COLUMNS - set(frame.columns)
        if missing:
            raise ValueError(f"TfL file {path.name} is missing columns: {sorted(missing)}")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def parse_duration_seconds(value: str) -> int:
    text = str(value).strip()
    parts = {part[-1]: int(part[:-1]) for part in text.split() if part and part[-1] in {"h", "m", "s"}}
    seconds = parts.get("h", 0) * 3600 + parts.get("m", 0) * 60 + parts.get("s", 0)
    if seconds <= 0:
        raise ValueError(f"Invalid TfL duration: {value!r}")
    return seconds


def parse_duration_or_none(value: str) -> int | None:
    try:
        return parse_duration_seconds(value)
    except ValueError:
        return None
