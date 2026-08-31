"""SQL-first query seam for the common, unfiltered mobility reads."""

from __future__ import annotations

from pathlib import Path
import duckdb


class DuckDbQueryAdapter:
    def __init__(self, connect):
        self._connect = connect

    def area_activity(self, path: Path, cells: list[str]) -> dict[str, dict[str, int]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT h3_cell, sum(starts) AS starts, sum(ends) AS ends FROM ("
                "SELECT origin_h3 AS h3_cell, count(*) AS starts, 0 AS ends FROM read_parquet(?) "
                "WHERE origin_h3 IN (SELECT * FROM UNNEST(?)) GROUP BY origin_h3 UNION ALL "
                "SELECT destination_h3 AS h3_cell, 0 AS starts, count(*) AS ends FROM read_parquet(?) "
                "WHERE destination_h3 IN (SELECT * FROM UNNEST(?)) GROUP BY destination_h3) GROUP BY h3_cell",
                [str(path), cells, str(path), cells],
            ).fetchall()
        return {row[0]: {"starts": int(row[1] or 0), "ends": int(row[2] or 0)} for row in rows}

    def hotspots(self, path: Path, metric: str, limit: int) -> list[tuple[str, int]]:
        column = "origin_h3" if metric == "starts" else "destination_h3"
        with self._connect() as connection:
            if metric in {"starts", "ends"}:
                return connection.execute(
                    f"SELECT {column} AS h3_cell, count(*) AS value FROM read_parquet(?) "
                    "GROUP BY 1 ORDER BY value DESC, h3_cell LIMIT ?", [str(path), limit]
                ).fetchall()
            return connection.execute(
                "SELECT h3_cell, count(*) AS value FROM (SELECT origin_h3 AS h3_cell FROM read_parquet(?) "
                "UNION ALL SELECT destination_h3 AS h3_cell FROM read_parquet(?)) GROUP BY h3_cell "
                "ORDER BY value DESC, h3_cell LIMIT ?", [str(path), str(path), limit]
            ).fetchall()
