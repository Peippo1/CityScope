from pydantic import BaseModel, Field


class ActivityCell(BaseModel):
    h3_cell: str
    latitude: float | None = None
    longitude: float | None = None
    total_journeys: int = Field(ge=0)
    origin_journeys: int = Field(ge=0)
    destination_journeys: int = Field(ge=0)


class ActivityResponse(BaseModel):
    city: str
    dataset_name: str | None = None
    observation_period: str
    attribution_text: str | None = None
    historical_snapshot: bool = True
    h3_resolution: int
    cells: list[ActivityCell]


class CityCapability(BaseModel):
    id: str
    name: str
    historical: bool
    routes: bool
    live_network: bool
    timezone: str
    bounds: tuple[float, float, float, float]


class CitiesResponse(BaseModel):
    cities: list[CityCapability]


class CityComparisonRow(BaseModel):
    city: str
    city_name: str
    value: float
    rank: int
    snapshot_id: str
    is_fixture: bool = False


class CityComparisonResponse(BaseModel):
    metric: str
    calculation_basis: str
    observation_period: str
    cities: list[CityComparisonRow]
    limitations: list[str]
