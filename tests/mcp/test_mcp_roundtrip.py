import asyncio

import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from services.city_data_mcp.server import app, mcp


def test_streamable_http_client_server_round_trip():
    async def run() -> None:
        transport = httpx.ASGITransport(app=app)
        async with mcp.session_manager.run():
            async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8001") as client:
                async with streamable_http_client("http://localhost:8001/mcp/", http_client=client) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        hotspots = await session.call_tool(
                            "find_hotspots",
                            {"request": {"city": "london", "metric": "total_activity", "limit": 2, "time_filter": {}}},
                        )
                        assert {tool.name for tool in tools.tools} == {
                            "describe_dataset", "get_area_metrics", "find_hotspots", "compare_areas"
                        }
                        assert hotspots.isError is False
                        assert hotspots.content

    asyncio.run(run())
