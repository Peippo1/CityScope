from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class CityDataMcpClient:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.getenv("CITYSCOPE_CITY_DATA_MCP_URL", "http://localhost:8001/mcp/")

    async def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with streamable_http_client(self.url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=20)) as session:
                await session.initialize()
                result = await session.call_tool(tool, {"request": arguments})
                if result.isError:
                    raise RuntimeError(f"City Data MCP tool failed: {tool}")
                structured = getattr(result, "structuredContent", None)
                if structured and isinstance(structured, dict):
                    payload = structured.get("result", structured)
                    if isinstance(payload, dict):
                        return payload
                raise RuntimeError(f"City Data MCP returned no structured result: {tool}")
