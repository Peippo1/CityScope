from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

from ..cities import get_city, historical_city_ids
from pipelines.core.analytics_contract import MetricName, TimeFilter
from .query_adapter import DuckDbQueryAdapter


COMPARISON_METRICS = {"trips_per_active_station_day", "median_trip_duration_minutes", "peak_hour_share", "weekend_share", "hotspot_concentration"}


class MobilityAnalytics:
    """Deterministic city analytics over independently versioned Parquet artifacts."""

    def __init__(self, root: Path, *, use_precomputed: bool = True):
        self.root = root
        self._comparison_cache: dict[tuple[str, str], float] = {}
        self._precomputed_comparison = self._load_precomputed_comparison() if use_precomputed else None
        self._query_adapter = DuckDbQueryAdapter(self._connect)

    @property
    def metadata_path(self) -> Path:
        """Compatibility accessor for the original London-only fixture tests."""
        return self._paths("london")[0]

    @property
    def journeys_path(self) -> Path:
        return self._paths("london")[1]

    def _paths(self, city: str) -> tuple[Path, Path]:
        get_city(city)
        metadata, generated = self.root / "data" / "metadata", self.root / "data" / "generated"
        production_metadata = metadata / f"{city}-cycling-production.json"
        production_journeys = generated / f"{city}_cycling_production_journeys.parquet"
        if production_metadata.exists() and production_journeys.exists():
            return production_metadata, production_journeys
        if city == "london":
            return metadata / "london-cycling-fixture.json", generated / "london_cycling_journeys.parquet"
        return metadata / f"{city}-cycling-fixture.json", generated / f"{city}_cycling_fixture_journeys.parquet"

    def _dataset(self, city: str) -> tuple[dict, Path]:
        metadata_path, journeys_path = self._paths(city)
        if not metadata_path.exists() or not journeys_path.exists():
            raise FileNotFoundError(f"Journey artifact for {city} is not built; run the multi-city fixture or production pipeline")
        return json.loads(metadata_path.read_text()), journeys_path

    def describe_dataset(self, city: str) -> dict:
        definition = get_city(city)
        if not definition.historical:
            raise ValueError(f"{definition.name} is available as live network context only")
        metadata, _ = self._dataset(city)
        return {
            "city": city, "dataset_id": metadata.get("dataset_id", metadata.get("dataset", "")), "dataset_name": metadata.get("dataset_name", metadata.get("dataset", "")), "snapshot_id": metadata.get("snapshot_id", "fixture"),
            "observation_start": metadata.get("observation_start", metadata.get("observation_period", "")), "observation_end": metadata.get("observation_end_exclusive", metadata.get("observation_period", "")), "source_organisation": metadata.get("source_organisation", ""),
            "mode": "cycle_hire", "available_metrics": ["starts", "ends", "total_activity", "journey_count", "city_percentile"], "supported_temporal_filters": ["start_date", "end_date", "weekdays", "hour_start", "hour_end", "weekend", "time_of_day"],
            "h3_resolution": metadata.get("h3_resolution", metadata.get("primary_h3_resolution", 9)), "limitations": ["Historical cycle-hire activity is not live cycling activity.", "Cross-city comparisons use normalized metrics, not raw trip totals."], "historical": True,
            "attribution_text": metadata.get("attribution_text"), "provenance_summary": {"source_url": metadata.get("source_url", definition.source_url), "licence_terms_reference": metadata.get("licence_terms_reference", definition.licence_reference), "source_files": [item.get("file") for item in metadata.get("source_files", [])]},
        }

    def get_area_metrics(self, city: str, h3_cells: list[str], metrics: list[MetricName], time_filter: TimeFilter) -> list[dict]:
        self._validate_cells(h3_cells)
        if not time_filter.start_date and not time_filter.end_date and not time_filter.weekdays and time_filter.hour_start is None and time_filter.hour_end is None and time_filter.weekend is None and not time_filter.time_of_day and set(metrics).issubset({"starts", "ends", "total_activity"}):
            _, journeys_path = self._dataset(city)
            values = self._query_adapter.area_activity(journeys_path, h3_cells)
            values = {cell: {**item, "total_activity": item["starts"] + item["ends"]} for cell, item in values.items()}
            return [{"h3_cell": cell, **{metric: values.get(cell, {}).get(metric, 0) for metric in metrics}} for cell in h3_cells]
        values = self._metric_values(self._filtered_journeys(city, time_filter), metrics)
        return [{"h3_cell": cell, **{metric: int(values[metric].get(cell, 0)) if metric != "city_percentile" else round(float(values[metric].get(cell, 0)), 4) for metric in metrics}} for cell in h3_cells]

    def find_hotspots(self, city: str, metric: MetricName, time_filter: TimeFilter, limit: int) -> list[dict]:
        if not time_filter.start_date and not time_filter.end_date and not time_filter.weekdays and time_filter.hour_start is None and time_filter.hour_end is None and time_filter.weekend is None and not time_filter.time_of_day and metric in {"starts", "ends", "total_activity"}:
            _, journeys_path = self._dataset(city)
            rows = self._query_adapter.hotspots(journeys_path, metric, limit)
            maximum = int(rows[0][1]) if rows else 0
            return [{"rank": index, "h3_cell": cell, "metric": metric, "value": int(value), "city_percentile": round(float(value / maximum), 4) if maximum else 0.0} for index, (cell, value) in enumerate(rows, start=1)]
        values = self._metric_values(self._filtered_journeys(city, time_filter), [metric])[metric]
        maximum = max(values.values(), default=0)
        return [{"rank": index, "h3_cell": cell, "metric": metric, "value": int(value) if metric != "city_percentile" else round(float(value), 4), "city_percentile": round(float(value / maximum), 4) if maximum else 0.0} for index, (cell, value) in enumerate(sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit], start=1)]

    def compare_areas(self, city: str, area_groups: list[dict], metrics: list[MetricName], time_filter: TimeFilter) -> list[dict]:
        values = self._metric_values(self._filtered_journeys(city, time_filter), metrics)
        groups = [{"group": group["group"], "h3_cells": group["h3_cells"], **{metric: sum(values[metric].get(cell, 0) for cell in group["h3_cells"]) for metric in metrics}} for group in area_groups]
        relative = {metric: None if groups[0][metric] == 0 else round((groups[1][metric] - groups[0][metric]) / groups[0][metric], 4) for metric in metrics} if len(groups) == 2 else {}
        return [{"groups": groups, "relative_difference": relative}]

    def compare_cities(self, cities: list[str], metric: str) -> dict:
        if metric not in COMPARISON_METRICS:
            raise ValueError("Unsupported cross-city metric")
        unique = list(dict.fromkeys(cities))
        if not 2 <= len(unique) <= 4 or any(city not in historical_city_ids() for city in unique):
            raise ValueError("Comparisons require two to four historical cohort cities")
        rows = []
        fixture_cities = []
        for city in unique:
            metadata, _ = self._dataset(city)
            is_fixture = metadata.get("snapshot_id", "").endswith("fixture")
            if is_fixture: fixture_cities.append(get_city(city).name)
            rows.append({"city": city, "city_name": get_city(city).name, "value": self._comparison_value(city, metric), "snapshot_id": metadata.get("snapshot_id", "unknown"), "is_fixture": is_fixture})
        rows.sort(key=lambda row: (-row["value"], row["city"]))
        for rank, row in enumerate(rows, 1): row["rank"] = rank
        limitations = ["Cities are compared using normalized metrics over a matched May 2026 window.", "Raw trip totals are intentionally excluded from cross-city rankings."]
        if fixture_cities: limitations.insert(0, f"Development fixture data is loaded for {', '.join(fixture_cities)}; ingest verified production artifacts before treating this comparison as a finding.")
        return {"metric": metric, "calculation_basis": self._comparison_basis(metric), "observation_period": "2026-05-01/2026-05-31", "cities": rows, "limitations": limitations}

    def _comparison_value(self, city: str, metric: str) -> float:
        cached = self._comparison_cache.get((city, metric))
        if cached is not None:
            return cached
        precomputed = self._precomputed_comparison or {}
        value = precomputed.get("metrics", {}).get(metric, {}).get(city)
        if not isinstance(value, (int, float)):
            value = self._uncached_comparison_value(city, metric)
        self._comparison_cache[(city, metric)] = value
        return value

    def _load_precomputed_comparison(self) -> dict | None:
        path = self.root / "data" / "generated" / "cross_city_comparison.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
            if payload.get("schema_version") != 1 or set(payload.get("metrics", {})) != COMPARISON_METRICS:
                return None
            expected = payload.get("source_fingerprints", {})
            for city in historical_city_ids():
                metadata, journeys = self._dataset(city)
                actual = {
                    "snapshot_id": metadata.get("snapshot_id"),
                    "artifact_version": metadata.get("generated_artifact_version"),
                    "artifact_name": journeys.name,
                }
                if expected.get(city) != actual:
                    return None
            return payload
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _uncached_comparison_value(self, city: str, metric: str) -> float:
        _, journeys_path = self._dataset(city)
        with self._connect() as connection:
            if metric == "trips_per_active_station_day":
                origin_column, destination_column = self._station_id_columns(connection, journeys_path)
                trips, stations = connection.execute(f"""
                    SELECT (SELECT count(*) FROM read_parquet(?)),
                    (SELECT count(*) FROM (
                        SELECT DISTINCT "{origin_column}" AS station FROM read_parquet(?) WHERE "{origin_column}" IS NOT NULL
                        UNION
                        SELECT DISTINCT "{destination_column}" AS station FROM read_parquet(?) WHERE "{destination_column}" IS NOT NULL
                    ))
                """, [str(journeys_path), str(journeys_path), str(journeys_path)]).fetchone()
                return round(float(trips) / max(int(stations), 1) / 31, 4)
            if metric == "median_trip_duration_minutes":
                value = connection.execute("SELECT median(duration_seconds) / 60 FROM read_parquet(?)", [str(journeys_path)]).fetchone()[0]
                return round(float(value or 0), 4)
            if metric == "peak_hour_share":
                value = connection.execute("SELECT avg(CASE WHEN hour IN (7, 8, 9, 16, 17, 18) THEN 1.0 ELSE 0.0 END) FROM read_parquet(?)", [str(journeys_path)]).fetchone()[0]
                return round(float(value or 0), 4)
            if metric == "weekend_share":
                value = connection.execute("SELECT avg(CASE WHEN is_weekend THEN 1.0 ELSE 0.0 END) FROM read_parquet(?)", [str(journeys_path)]).fetchone()[0]
                return round(float(value or 0), 4)
            counts = connection.execute("""
                SELECT h3_cell, count(DISTINCT trip_id) AS value FROM (
                    SELECT trip_id, origin_h3 AS h3_cell FROM read_parquet(?)
                    UNION ALL
                    SELECT trip_id, destination_h3 AS h3_cell FROM read_parquet(?)
                ) GROUP BY h3_cell ORDER BY value DESC, h3_cell ASC
            """, [str(journeys_path), str(journeys_path)]).fetchall()
            top_cells = [row[0] for row in counts[:max(1, -(-len(counts) // 10))]]
            trip_count, concentrated_trips = connection.execute("""
                SELECT count(*), count(*) FILTER (
                    WHERE origin_h3 IN (SELECT * FROM UNNEST(?))
                       OR destination_h3 IN (SELECT * FROM UNNEST(?))
                )
                FROM read_parquet(?)
            """, [top_cells, top_cells, str(journeys_path)]).fetchone()
        return round(float(concentrated_trips) / max(int(trip_count), 1), 4)

    @staticmethod
    def _station_id_columns(connection: duckdb.DuckDBPyConnection, journeys_path: Path) -> tuple[str, str]:
        columns = {row[0] for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(journeys_path)]).fetchall()}
        for pair in (("origin_location_id", "destination_location_id"), ("origin_station_id", "destination_station_id")):
            if set(pair).issubset(columns):
                return pair
        raise ValueError("Journey artifact is missing origin and destination station identifiers")

    @staticmethod
    def _comparison_basis(metric: str) -> str:
        return {"trips_per_active_station_day": "completed trips divided by active origin/destination stations and 31 observation days", "median_trip_duration_minutes": "median completed-trip duration in minutes", "peak_hour_share": "share of trips beginning during 07:00-09:59 or 16:00-18:59 local source time", "weekend_share": "share of trips beginning on Saturday or Sunday local source time", "hotspot_concentration": "share of trips touching the busiest 10% of active H3 cells"}[metric]

    def _filtered_journeys(self, city: str, time_filter: TimeFilter) -> pd.DataFrame:
        _, journeys_path = self._dataset(city)
        conditions, params = [], [str(journeys_path)]
        if time_filter.start_date: conditions.append("CAST(start_timestamp AS DATE) >= ?"); params.append(time_filter.start_date)
        if time_filter.end_date: conditions.append("CAST(start_timestamp AS DATE) <= ?"); params.append(time_filter.end_date)
        if time_filter.weekdays: conditions.append("weekday IN (SELECT * FROM UNNEST(?))"); params.append(time_filter.weekdays)
        if time_filter.hour_start is not None: conditions.append("hour >= ?"); params.append(time_filter.hour_start)
        if time_filter.hour_end is not None: conditions.append("hour < ?"); params.append(time_filter.hour_end)
        if time_filter.weekend is True: conditions.append("is_weekend")
        elif time_filter.weekend is False: conditions.append("NOT is_weekend")
        if time_filter.time_of_day: conditions.append("time_of_day IN (SELECT * FROM UNNEST(?))"); params.append(time_filter.time_of_day)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as connection: return connection.execute("SELECT * FROM read_parquet(?)" + where, params).df()

    @staticmethod
    def _connect() -> duckdb.DuckDBPyConnection:
        connection = duckdb.connect()
        connection.execute("SET temp_directory='/tmp/cityscope-duckdb'")
        return connection

    @staticmethod
    def _metric_values(frame: pd.DataFrame, metrics: Iterable[MetricName]) -> dict[str, dict[str, int | float]]:
        starts = frame[["trip_id", "origin_h3"]].rename(columns={"origin_h3": "h3_cell"}); ends = frame[["trip_id", "destination_h3"]].rename(columns={"destination_h3": "h3_cell"}); events = pd.concat([starts, ends], ignore_index=True)
        result: dict[str, dict[str, int | float]] = {}
        for metric in metrics:
            grouped = starts.groupby("h3_cell").size() if metric == "starts" else ends.groupby("h3_cell").size() if metric == "ends" else events.drop_duplicates(["trip_id", "h3_cell"]).groupby("h3_cell").size() if metric == "journey_count" else events.groupby("h3_cell").size()
            values = grouped.astype(int).to_dict()
            if metric == "city_percentile":
                ordered = sorted(values.values()); values = {cell: (ordered.index(value) + 1) / len(ordered) for cell, value in values.items()} if ordered else {}
            result[metric] = values
        return result

    @staticmethod
    def _validate_cells(cells: list[str]) -> None:
        from h3 import is_valid_cell
        if not cells or len(cells) > 50 or any(not is_valid_cell(cell) for cell in cells): raise ValueError("Every H3 cell must be valid and at most 50 may be requested")
