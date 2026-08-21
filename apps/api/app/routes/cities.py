import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from ..analytics.duckdb_reader import ActivityReader
from ..schemas import ActivityResponse

ROOT = Path(__file__).resolve().parents[4]
router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("/{city}/activity", response_model=ActivityResponse)
def get_activity(city: str, limit: int = Query(default=100, ge=1, le=500)) -> ActivityResponse:
    if city != "london":
        raise HTTPException(status_code=404, detail="Only London is available in this vertical slice")
    metadata = json.loads((ROOT / "data" / "metadata" / "london-cycling-fixture.json").read_text())
    parquet = ROOT / "data" / "generated" / "london_cycling_activity.parquet"
    if not parquet.exists():
        raise HTTPException(status_code=503, detail="Dataset artifact is not built")
    return ActivityResponse(
        city=city,
        observation_period=metadata["observation_period"],
        h3_resolution=metadata["primary_h3_resolution"],
        cells=ActivityReader(parquet).activity(limit),
    )
