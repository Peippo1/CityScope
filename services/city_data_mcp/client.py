from __future__ import annotations

from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def inspect_server(url: str = "http://localhost:8001/mcp/") -> dict[str, Any]:
    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            calls = {}
            for name, arguments in [
                ("describe_dataset", {"request": {"city": "london"}}),
                ("find_hotspots", {"request": {"city": "london", "metric": "total_activity", "limit": 5, "time_filter": {}}}),
            ]:
                calls[name] = await session.call_tool(name, arguments)
            return {"tools": [tool.name for tool in tools.tools], "calls": calls}
