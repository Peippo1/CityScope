from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from pipelines.core.analytics_contract import TimeFilter

from ..analytics.mobility import MobilityAnalytics
from ..agent.live_mcp_client import CityLiveMcpClient
from ..cities import CITIES, historical_city_ids
from ..schemas import ActivityCell, ActivityResponse, CitiesResponse, CityCapability, CityComparisonResponse


ROOT = Path(__file__).resolve().parents[4]
router = APIRouter(prefix="/cities", tags=["cities"])
ANALYTICS = MobilityAnalytics(ROOT)


@router.get("", response_model=CitiesResponse)
def list_cities() -> CitiesResponse:
    return CitiesResponse(cities=[CityCapability(id=city.id, name=city.name, historical=city.historical, routes=city.routes, live_network=city.live_network, timezone=city.timezone, bounds=city.bounds) for city in CITIES.values()])


@router.get("/compare", response_model=CityComparisonResponse)
def compare_cities(cities: list[str] = Query(default=list(historical_city_ids())), metric: str = Query(default="trips_per_active_station_day")) -> CityComparisonResponse:
    try:
        return CityComparisonResponse(**ANALYTICS.compare_cities(cities, metric))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{city}/activity", response_model=ActivityResponse)
def get_activity(city: str, limit: int = Query(default=100, ge=1, le=500)) -> ActivityResponse:
    if city not in historical_city_ids():
        raise HTTPException(status_code=404, detail="Historical activity is unavailable for this city")
    try:
        dataset = ANALYTICS.describe_dataset(city)
        rows = ANALYTICS.find_hotspots(city, "total_activity", TimeFilter(), limit)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ActivityResponse(
        city=city, dataset_name=dataset["dataset_name"], observation_period="2026-05-01/2026-05-31",
        attribution_text=dataset["attribution_text"], historical_snapshot=True, h3_resolution=dataset["h3_resolution"],
        cells=[ActivityCell(h3_cell=row["h3_cell"], total_journeys=int(row["value"]), origin_journeys=0, destination_journeys=0) for row in rows],
    )


@router.get("/paris/live-network")
async def paris_live_network(limit: int = Query(default=25, ge=1, le=100)) -> dict:
    """Expose current operational status through the isolated live-data MCP boundary."""
    try:
        return await CityLiveMcpClient().get_paris_status(limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Paris live network data is temporarily unavailable") from exc
