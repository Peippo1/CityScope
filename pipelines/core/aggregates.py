import pandas as pd


def activity_aggregate(journeys: pd.DataFrame) -> pd.DataFrame:
    origins = journeys[["origin_h3", "trip_id"]].rename(columns={"origin_h3": "h3_cell"})
    destinations = journeys[["destination_h3", "trip_id"]].rename(columns={"destination_h3": "h3_cell"})
    activity = pd.concat([origins, destinations]).groupby("h3_cell", as_index=False).agg(
        total_journeys=("trip_id", "count")
    )
    origin_counts = origins.groupby("h3_cell").size().rename("origin_journeys")
    destination_counts = destinations.groupby("h3_cell").size().rename("destination_journeys")
    return (
        activity.join(origin_counts, on="h3_cell")
        .join(destination_counts, on="h3_cell")
        .fillna(0)
        .astype({"origin_journeys": int, "destination_journeys": int})
        .sort_values(["total_journeys", "h3_cell"], ascending=[False, True])
        .reset_index(drop=True)
    )
