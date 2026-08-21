from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from .schemas import AreaMetricsRequest, CompareAreasRequest, DatasetRequest, HotspotsRequest, DatasetMetadata, ToolEnvelope
from .tools import compare_areas, describe_dataset, find_hotspots, get_area_metrics

mcp = FastMCP("CityScope City Data", json_response=True, stateless_http=True, streamable_http_path="/")


@mcp.tool(name="describe_dataset")
def describe_dataset_tool(request: DatasetRequest) -> DatasetMetadata:
    """Describe the supported historical CityScope dataset."""
    return describe_dataset(request)


@mcp.tool(name="get_area_metrics")
def get_area_metrics_tool(request: AreaMetricsRequest) -> ToolEnvelope:
    """Return deterministic metrics for bounded H3 cells."""
    return get_area_metrics(request)


@mcp.tool(name="find_hotspots")
def find_hotspots_tool(request: HotspotsRequest) -> ToolEnvelope:
    """Return ranked H3 activity hotspots."""
    return find_hotspots(request)


@mcp.tool(name="compare_areas")
def compare_areas_tool(request: CompareAreasRequest) -> ToolEnvelope:
    """Compare bounded H3 area groups using deterministic metrics."""
    return compare_areas(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="CityScope City Data MCP", lifespan=lifespan)
app.mount("/mcp", mcp.streamable_http_app())
