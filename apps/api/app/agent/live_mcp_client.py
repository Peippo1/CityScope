from __future__ import annotations

import os
import asyncio
from datetime import timedelta
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class CityLiveMcpClient:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.getenv("CITYSCOPE_CITY_LIVE_DATA_MCP_URL", "http://localhost:8002/mcp/")

    async def _http_client(self) -> httpx.AsyncClient:
        audience = os.getenv("CITYSCOPE_CITY_LIVE_DATA_MCP_ID_TOKEN_AUDIENCE")
        headers: dict[str, str] = {}
        if audience:
            from google.auth.transport.requests import Request
            from google.oauth2.id_token import fetch_id_token
            headers["Authorization"] = f"Bearer {await asyncio.to_thread(fetch_id_token, Request(), audience)}"
        return httpx.AsyncClient(headers=headers, timeout=20)

    async def get_paris_status(self, limit: int = 25) -> dict[str, Any]:
        async with await self._http_client() as client:
            async with streamable_http_client(self.url, http_client=client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=20)) as session:
                    await session.initialize()
                    result = await session.call_tool("get_live_station_status", {"request": {"city": "paris", "limit": limit}})
        if result.isError: raise RuntimeError("City Live Data MCP tool failed")
        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            payload = structured.get("result", structured)
            if isinstance(payload, dict): return payload
        raise RuntimeError("City Live Data MCP returned no structured result")
