import pandas as pd


def add_temporal_features(frame: pd.DataFrame, timestamp_column: str = "start_timestamp") -> pd.DataFrame:
    result = frame.copy()
    timestamps = pd.to_datetime(result[timestamp_column], utc=True)
    result["hour"] = timestamps.dt.hour
    result["weekday"] = timestamps.dt.day_name()
    result["is_weekend"] = timestamps.dt.dayofweek >= 5
    result["month"] = timestamps.dt.month
    result["time_of_day"] = timestamps.dt.hour.map(time_of_day)
    result["duration_band"] = pd.cut(
        result["duration_seconds"],
        bins=[0, 300, 900, 1800, float("inf")],
        labels=["short", "medium", "long", "very_long"],
        include_lowest=True,
    ).astype(str)
    return result


def time_of_day(hour: int) -> str:
    if hour < 6:
        return "night"
    if hour < 9:
        return "morning_commute"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "midday"
    if hour < 20:
        return "evening_commute"
    return "evening"
