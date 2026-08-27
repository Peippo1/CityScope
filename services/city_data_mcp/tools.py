from pathlib import Path

from apps.api.app.analytics.mobility import MobilityAnalytics

from .schemas import (
    AreaMetricsRequest,
    CompareCitiesRequest,
    CityComparisonResponse,
    CompareAreasRequest,
    DatasetMetadata,
    DatasetRequest,
    Evidence,
    HotspotsRequest,
    MapLayer,
    ToolEnvelope,
)


ANALYTICS = MobilityAnalytics(Path(__file__).resolve().parents[2])


def describe_dataset(request: DatasetRequest) -> DatasetMetadata:
    return DatasetMetadata.model_validate(ANALYTICS.describe_dataset(request.city))


def get_area_metrics(request: AreaMetricsRequest) -> ToolEnvelope:
    results = ANALYTICS.get_area_metrics(request.city, request.h3_cells, request.metrics, request.time_filter)
    dataset = DatasetMetadata.model_validate(ANALYTICS.describe_dataset(request.city))
    evidence = [
        Evidence(metric=metric, value=row[metric], unit="journeys", source_aggregate="canonical_journey_h3_activity", filters_applied=request.time_filter.model_dump(mode="json"), h3_cells=[row["h3_cell"]])
        for row in results
        for metric in request.metrics
    ]
    layers = [MapLayer(h3_cell=row["h3_cell"], metric=metric, value=row[metric]) for row in results for metric in request.metrics if metric != "city_percentile"]
    return ToolEnvelope(dataset=dataset, results=results, evidence=evidence, map_layers=layers, limitations=dataset.limitations)


def find_hotspots(request: HotspotsRequest) -> ToolEnvelope:
    results = ANALYTICS.find_hotspots(request.city, request.metric, request.time_filter, request.limit)
    dataset = DatasetMetadata.model_validate(ANALYTICS.describe_dataset(request.city))
    filters = request.time_filter.model_dump(mode="json")
    evidence = [Evidence(metric=request.metric, value=row["value"], unit="journeys", source_aggregate="canonical_journey_h3_activity", filters_applied=filters, h3_cells=[row["h3_cell"]]) for row in results]
    layers = [MapLayer(h3_cell=row["h3_cell"], metric=request.metric, value=row["value"], rank=row["rank"]) for row in results]
    return ToolEnvelope(dataset=dataset, results=results, evidence=evidence, map_layers=layers, limitations=dataset.limitations)


def compare_areas(request: CompareAreasRequest) -> ToolEnvelope:
    results = ANALYTICS.compare_areas(request.city, [group.model_dump() for group in request.area_groups], request.metrics, request.time_filter)
    dataset = DatasetMetadata.model_validate(ANALYTICS.describe_dataset(request.city))
    groups = results[0]["groups"]
    filters = request.time_filter.model_dump(mode="json")
    evidence = [Evidence(metric=metric, value=group[metric], unit="journeys", source_aggregate="canonical_journey_h3_activity", filters_applied=filters, h3_cells=group["h3_cells"]) for group in groups for metric in request.metrics]
    layers = [MapLayer(h3_cell=cell, metric="area", value=1) for group in groups for cell in group["h3_cells"]]
    return ToolEnvelope(dataset=dataset, results=results, evidence=evidence, map_layers=layers, limitations=dataset.limitations)


def compare_cities(request: CompareCitiesRequest) -> CityComparisonResponse:
    """Return normalized, matched-window metrics only; raw volume rankings are forbidden."""
    return CityComparisonResponse.model_validate(ANALYTICS.compare_cities(request.cities, request.metric))
