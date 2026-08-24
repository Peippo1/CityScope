from __future__ import annotations

import os
import asyncio
from datetime import timedelta
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class CityDataMcpClient:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.getenv("CITYSCOPE_CITY_DATA_MCP_URL", "http://localhost:8001/mcp/")

    async def _http_client(self) -> httpx.AsyncClient:
        audience = os.getenv("CITYSCOPE_CITY_DATA_MCP_ID_TOKEN_AUDIENCE")
        headers: dict[str, str] = {}
        if audience:
            from google.auth.transport.requests import Request
            from google.oauth2.id_token import fetch_id_token

            token = await asyncio.to_thread(fetch_id_token, Request(), audience)
            headers["Authorization"] = f"Bearer {token}"
        return httpx.AsyncClient(headers=headers, timeout=20)

    async def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with await self._http_client() as http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (read_stream, write_stream, _):
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
