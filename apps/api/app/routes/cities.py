from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from h3 import cell_to_latlng

from pipelines.core.analytics_contract import TimeFilter

from ..analytics.mobility import MobilityAnalytics
from ..agent.live_mcp_client import CityLiveMcpClient
from ..cities import CITIES, get_city, historical_city_ids, nearest_area_name
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
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Cross-city comparison is temporarily unavailable") from exc


@router.get("/{city}/activity", response_model=ActivityResponse)
def get_activity(city: str, limit: int = Query(default=50, ge=1, le=50)) -> ActivityResponse:
    if city not in historical_city_ids():
        raise HTTPException(status_code=404, detail="Historical activity is unavailable for this city")
    try:
        dataset = ANALYTICS.describe_dataset(city)
        rows = ANALYTICS.find_hotspots(city, "total_activity", TimeFilter(), limit)
        area_metrics = {row["h3_cell"]: row for row in ANALYTICS.get_area_metrics(city, [item["h3_cell"] for item in rows], ["starts", "ends"], TimeFilter())}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ActivityResponse(
        city=city, dataset_name=dataset["dataset_name"], observation_period="2026-05-01/2026-05-31",
        attribution_text=dataset["attribution_text"], historical_snapshot=True, h3_resolution=dataset["h3_resolution"],
        cells=[ActivityCell(h3_cell=row["h3_cell"], area_name=nearest_area_name(city, *cell_to_latlng(row["h3_cell"])), latitude=cell_to_latlng(row["h3_cell"])[0], longitude=cell_to_latlng(row["h3_cell"])[1], total_journeys=int(row["value"]), origin_journeys=int(area_metrics[row["h3_cell"]]["starts"]), destination_journeys=int(area_metrics[row["h3_cell"]]["ends"])) for row in rows],
    )


@router.get("/{city}/live-network")
async def live_network(city: str, limit: int = Query(default=25, ge=1, le=100)) -> dict:
    """Expose current operational status through the isolated live-data MCP boundary."""
    try:
        definition = get_city(city)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Live network data is unavailable for this city") from exc
    if not definition.live_network:
        raise HTTPException(status_code=404, detail="Live network data is unavailable for this city")
    try:
        return await CityLiveMcpClient().get_status(city, limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"{definition.name} live network data is temporarily unavailable") from exc
