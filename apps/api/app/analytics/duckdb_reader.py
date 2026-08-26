from pathlib import Path

import duckdb


class ActivityReader:
    def __init__(self, parquet_path: Path):
        self.parquet_path = parquet_path

    def activity(self, limit: int = 100) -> list[dict]:
        safe_limit = min(max(limit, 1), 500)
        with duckdb.connect() as connection:
            relation = connection.execute(
                "SELECT h3_cell, total_journeys, origin_journeys, destination_journeys "
                "FROM read_parquet(?) ORDER BY total_journeys DESC, h3_cell ASC LIMIT ?",
                [str(self.parquet_path), safe_limit],
            )
            return relation.df().to_dict(orient="records")
