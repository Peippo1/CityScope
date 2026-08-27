import asyncio

import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from services.city_data_mcp.server import app, mcp, transport_security_settings


def test_transport_security_accepts_configured_cloud_run_hosts(monkeypatch):
    monkeypatch.setenv(
        "CITYSCOPE_MCP_ALLOWED_HOSTS",
        "cityscope-mcp-329540911678.europe-west2.run.app, localhost:* ",
    )

    settings = transport_security_settings()

    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == [
        "cityscope-mcp-329540911678.europe-west2.run.app",
        "localhost:*",
    ]


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
                        comparison = await session.call_tool(
                            "compare_cities",
                            {"request": {"cities": ["london", "chicago"], "metric": "hotspot_concentration"}},
                        )
                        assert {tool.name for tool in tools.tools} == {
                            "describe_dataset", "get_area_metrics", "find_hotspots", "compare_areas", "compare_cities"
                        }
                        assert hotspots.isError is False
                        assert hotspots.content
                        assert comparison.isError is False
                        assert comparison.structuredContent["metric"] == "hotspot_concentration"
                        assert len(comparison.structuredContent["cities"]) == 2

    asyncio.run(run())
