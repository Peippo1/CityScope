from pydantic import BaseModel, Field


class ActivityCell(BaseModel):
    h3_cell: str
    total_journeys: int = Field(ge=0)
    origin_journeys: int = Field(ge=0)
    destination_journeys: int = Field(ge=0)


class ActivityResponse(BaseModel):
    city: str
    observation_period: str
    h3_resolution: int
    cells: list[ActivityCell]
