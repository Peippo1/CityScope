from pydantic import BaseModel, Field


class ActivityCell(BaseModel):
    h3_cell: str
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
