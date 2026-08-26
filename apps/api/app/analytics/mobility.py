from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

from pipelines.core.analytics_contract import MetricName, TimeFilter


class MobilityAnalytics:
    """Shared deterministic analytics used by both HTTP and MCP consumers."""

    def __init__(self, root: Path):
        self.root = root
        production = root / "data" / "metadata" / "london-cycling-production.json"
        fixture = root / "data" / "metadata" / "london-cycling-fixture.json"
        production_journeys = root / "data" / "generated" / "london_cycling_production_journeys.parquet"
        fixture_journeys = root / "data" / "generated" / "london_cycling_journeys.parquet"
        # Clean CI and new checkouts intentionally do not contain licensed raw data.
        # Use production metadata only when its corresponding artifact is present.
        use_production = production.exists() and production_journeys.exists()
        self.metadata_path = production if use_production else fixture
        self.metadata = json.loads(self.metadata_path.read_text())
        production_activity = root / "data" / "generated" / "london_cycling_activity.parquet"
        fixture_activity = root / "data" / "generated" / "london_cycling_fixture_activity.parquet"
        self.parquet_path = production_activity if use_production else fixture_activity
        self.journeys_path = production_journeys if use_production else fixture_journeys

    def describe_dataset(self, city: str) -> dict:
        self._validate_city(city)
        return {
            "city": city,
            "dataset_id": self.metadata.get("dataset_id", self.metadata.get("dataset", "")),
            "dataset_name": self.metadata.get("dataset_name", self.metadata.get("dataset", "")),
            "snapshot_id": self.metadata.get("snapshot_id", "fixture"),
            "observation_start": self.metadata.get("observation_start", self.metadata.get("observation_period", "")),
            "observation_end": self.metadata.get("observation_end_exclusive", self.metadata.get("observation_period", "")),
            "source_organisation": self.metadata.get("source_organisation", ""),
            "mode": "cycle_hire",
            "available_metrics": ["starts", "ends", "total_activity", "journey_count", "city_percentile"],
            "supported_temporal_filters": ["start_date", "end_date", "weekdays", "hour_start", "hour_end", "weekend", "time_of_day"],
            "h3_resolution": self.metadata.get("h3_resolution", self.metadata.get("primary_h3_resolution", 9)),
            "limitations": [
                "Historical cycle-hire activity is not live cycling activity.",
                "Station records without a matching authoritative coordinate were quarantined during ingestion.",
            ],
            "historical": self.metadata.get("historical_snapshot", True),
            "attribution_text": self.metadata.get("attribution_text"),
            "provenance_summary": {
                "source_url": self.metadata.get("source_url"),
                "licence_terms_reference": self.metadata.get("licence_terms_reference"),
                "source_files": [item.get("file") for item in self.metadata.get("source_files", [])],
            },
        }

    def get_area_metrics(self, city: str, h3_cells: list[str], metrics: list[MetricName], time_filter: TimeFilter) -> list[dict]:
        self._validate_city(city)
        self._validate_cells(h3_cells)
        frame = self._filtered_journeys(time_filter)
        values = self._metric_values(frame, metrics)
        rows = []
        for cell in h3_cells:
            row = {"h3_cell": cell}
            for metric in metrics:
                value = float(values[metric].get(cell, 0))
                row[metric] = int(value) if metric != "city_percentile" else round(value, 4)
            rows.append(row)
        return rows

    def find_hotspots(self, city: str, metric: MetricName, time_filter: TimeFilter, limit: int) -> list[dict]:
        self._validate_city(city)
        frame = self._filtered_journeys(time_filter)
        values = self._metric_values(frame, [metric])[metric]
        ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit]
        max_value = max(values.values(), default=0)
        return [
            {
                "rank": index,
                "h3_cell": cell,
                "metric": metric,
                "value": int(value) if metric != "city_percentile" else round(float(value), 4),
                "city_percentile": round(float(value / max_value), 4) if max_value else 0.0,
            }
            for index, (cell, value) in enumerate(ranked, start=1)
        ]

    def compare_areas(self, city: str, area_groups: list[dict], metrics: list[MetricName], time_filter: TimeFilter) -> list[dict]:
        self._validate_city(city)
        frame = self._filtered_journeys(time_filter)
        values = self._metric_values(frame, metrics)
        results = []
        for group in area_groups:
            row = {"group": group["group"], "h3_cells": group["h3_cells"]}
            for cell in group["h3_cells"]:
                self._validate_cells([cell])
            for metric in metrics:
                row[metric] = sum(values[metric].get(cell, 0) for cell in group["h3_cells"])
            results.append(row)
        if len(results) == 2:
            baseline, comparison = results
            relative = {}
            for metric in metrics:
                base = baseline[metric]
                relative[metric] = None if base == 0 else round((comparison[metric] - base) / base, 4)
            return [{"groups": results, "relative_difference": relative}]
        return [{"groups": results, "relative_difference": {}}]

    def _filtered_journeys(self, time_filter: TimeFilter) -> pd.DataFrame:
        if not self.journeys_path.exists():
            raise FileNotFoundError("Journey artifact is not built; run the fixture or production pipeline")
        conditions = []
        params: list[object] = [str(self.journeys_path)]
        if time_filter.start_date:
            conditions.append("CAST(start_timestamp AS DATE) >= ?")
            params.append(time_filter.start_date)
        if time_filter.end_date:
            conditions.append("CAST(start_timestamp AS DATE) <= ?")
            params.append(time_filter.end_date)
        if time_filter.weekdays:
            conditions.append("dayname(start_timestamp) IN (SELECT * FROM UNNEST(?))")
            params.append(time_filter.weekdays)
        if time_filter.hour_start is not None:
            conditions.append("EXTRACT(HOUR FROM start_timestamp) >= ?")
            params.append(time_filter.hour_start)
        if time_filter.hour_end is not None:
            conditions.append("EXTRACT(HOUR FROM start_timestamp) < ?")
            params.append(time_filter.hour_end)
        if time_filter.weekend is True:
            conditions.append("dayname(start_timestamp) IN ('Saturday', 'Sunday')")
        elif time_filter.weekend is False:
            conditions.append("dayname(start_timestamp) NOT IN ('Saturday', 'Sunday')")
        if time_filter.time_of_day:
            conditions.append("time_of_day IN (SELECT * FROM UNNEST(?))")
            params.append(time_filter.time_of_day)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = "SELECT trip_id, origin_h3, destination_h3 FROM read_parquet(?)" + where
        with duckdb.connect() as connection:
            return connection.execute(sql, params).df()

    @staticmethod
    def _metric_values(frame: pd.DataFrame, metrics: Iterable[MetricName]) -> dict[str, dict[str, int | float]]:
        starts = frame[["trip_id", "origin_h3"]].rename(columns={"origin_h3": "h3_cell"})
        ends = frame[["trip_id", "destination_h3"]].rename(columns={"destination_h3": "h3_cell"})
        events = pd.concat([starts, ends], ignore_index=True)
        output: dict[str, dict[str, int | float]] = {}
        for metric in metrics:
            if metric == "starts":
                grouped = starts.groupby("h3_cell").size()
            elif metric == "ends":
                grouped = ends.groupby("h3_cell").size()
            elif metric == "journey_count":
                grouped = events.drop_duplicates(["trip_id", "h3_cell"]).groupby("h3_cell").size()
            else:
                grouped = events.groupby("h3_cell").size()
            values = grouped.astype(int).to_dict()
            if metric == "city_percentile":
                ordered = sorted(values.values())
                values = {cell: (ordered.index(value) + 1) / len(ordered) if ordered else 0.0 for cell, value in values.items()}
            output[metric] = values
        return output

    def _validate_city(self, city: str) -> None:
        if city != "london":
            raise ValueError("Unsupported city: only london is available")

    @staticmethod
    def _validate_cells(h3_cells: list[str]) -> None:
        from h3 import is_valid_cell

        if not h3_cells or len(h3_cells) > 50:
            raise ValueError("h3_cells must contain between 1 and 50 cells")
        if any(not is_valid_cell(cell) for cell in h3_cells):
            raise ValueError("Every h3 cell must be a valid H3 identifier")
