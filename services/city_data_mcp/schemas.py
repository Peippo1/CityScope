from typing import Literal

from h3 import is_valid_cell
from pydantic import BaseModel, Field, field_validator
from pipelines.core.analytics_contract import MetricName, TimeFilter

HistoricalCityId = Literal["london", "new_york", "chicago", "washington_dc"]


class DatasetRequest(BaseModel):
    city: HistoricalCityId


class AreaMetricsRequest(BaseModel):
    city: HistoricalCityId
    h3_cells: list[str] = Field(min_length=1, max_length=50)
    metrics: list[MetricName] = Field(min_length=1, max_length=5)
    time_filter: TimeFilter = Field(default_factory=TimeFilter)

    @field_validator("h3_cells")
    @classmethod
    def validate_h3_cells(cls, value: list[str]) -> list[str]:
        if any(not is_valid_cell(cell) for cell in value):
            raise ValueError("Every h3 cell must be a valid H3 identifier")
        return value


class HotspotsRequest(BaseModel):
    city: HistoricalCityId
    metric: MetricName
    time_filter: TimeFilter = Field(default_factory=TimeFilter)
    limit: int = Field(default=10, ge=1, le=50)


class AreaGroup(BaseModel):
    group: str = Field(min_length=1, max_length=80)
    h3_cells: list[str] = Field(min_length=1, max_length=50)

    @field_validator("h3_cells")
    @classmethod
    def validate_h3_cells(cls, value: list[str]) -> list[str]:
        if any(not is_valid_cell(cell) for cell in value):
            raise ValueError("Every h3 cell must be a valid H3 identifier")
        return value


class CompareAreasRequest(BaseModel):
    city: HistoricalCityId
    area_groups: list[AreaGroup] = Field(min_length=2, max_length=8)
    metrics: list[MetricName] = Field(min_length=1, max_length=5)
    time_filter: TimeFilter = Field(default_factory=TimeFilter)


ComparisonMetric = Literal["trips_per_active_station_day", "median_trip_duration_minutes", "peak_hour_share", "weekend_share", "hotspot_concentration"]


class CompareCitiesRequest(BaseModel):
    cities: list[HistoricalCityId] = Field(min_length=2, max_length=4)
    metric: ComparisonMetric = "trips_per_active_station_day"


class CityComparisonRow(BaseModel):
    city: HistoricalCityId
    city_name: str
    value: float
    rank: int
    snapshot_id: str
    is_fixture: bool = False


class CityComparisonResponse(BaseModel):
    metric: ComparisonMetric
    calculation_basis: str
    observation_period: str
    cities: list[CityComparisonRow]
    limitations: list[str]


class DatasetMetadata(BaseModel):
    city: str
    dataset_id: str
    dataset_name: str
    snapshot_id: str
    observation_start: str
    observation_end: str
    source_organisation: str
    mode: str
    h3_resolution: int
    historical: bool
    attribution_text: str | None = None
    available_metrics: list[str]
    supported_temporal_filters: list[str]
    limitations: list[str]
    provenance_summary: dict


class Evidence(BaseModel):
    source: Literal["city_data", "google_maps"] = "city_data"
    metric: str
    value: int | float
    unit: str
    source_aggregate: str
    filters_applied: dict
    h3_cells: list[str] = Field(default_factory=list)
    category: str | None = None
    search_radius_m: int | None = None


class MapLayer(BaseModel):
    h3_cell: str
    metric: str
    value: int | float
    rank: int | None = None


class ToolEnvelope(BaseModel):
    dataset: DatasetMetadata
    results: list[dict]
    evidence: list[Evidence]
    map_layers: list[MapLayer]
    limitations: list[str]
