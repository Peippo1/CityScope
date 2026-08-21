import asyncio
from pathlib import Path

import pytest
from h3 import latlng_to_cell
from pydantic import ValidationError

from services.city_data_mcp.schemas import AreaMetricsRequest, CompareAreasRequest, HotspotsRequest, TimeFilter
from services.city_data_mcp.server import mcp
from services.city_data_mcp.tools import compare_areas, find_hotspots, get_area_metrics


LONDON_CELL = latlng_to_cell(51.5074, -0.1278, 9)


def test_server_discovers_exact_v1_tools():
    names = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert names == {"describe_dataset", "get_area_metrics", "find_hotspots", "compare_areas"}


def test_tool_inputs_reject_invalid_city_cells_and_limits():
    with pytest.raises(ValidationError):
        HotspotsRequest(city="paris", metric="starts")
    with pytest.raises(ValidationError):
        AreaMetricsRequest(city="london", h3_cells=["not-h3"], metrics=["starts"])
    with pytest.raises(ValidationError):
        HotspotsRequest(city="london", metric="starts", limit=51)
    with pytest.raises(ValidationError):
        TimeFilter(start_date="2026-06-01", end_date="2026-05-01")


def test_hotspot_result_has_metadata_evidence_and_map_layer():
    result = find_hotspots(HotspotsRequest(city="london", metric="total_activity", limit=3))

    assert result.dataset.historical is True
    assert result.evidence
    assert result.map_layers
    assert len(result.results) == 3
    assert result.results[0]["rank"] == 1


def test_area_metrics_matches_hotspot_value_for_same_cell():
    hotspot = find_hotspots(HotspotsRequest(city="london", metric="total_activity", limit=1))
    cell = hotspot.results[0]["h3_cell"]
    area = get_area_metrics(AreaMetricsRequest(city="london", h3_cells=[cell], metrics=["total_activity"]))

    assert area.results[0]["total_activity"] == hotspot.results[0]["value"]
    assert area.map_layers[0].h3_cell == cell


def test_compare_areas_returns_relative_difference():
    result = compare_areas(CompareAreasRequest(
        city="london",
        area_groups=[
            {"group": "central", "h3_cells": [LONDON_CELL]},
            {"group": "other", "h3_cells": ["89194ad3267ffff"]},
        ],
        metrics=["starts", "ends"],
    ))

    assert len(result.results[0]["groups"]) == 2
    assert "starts" in result.results[0]["relative_difference"]
