"""Bounded in-process admission control; Cloud Armor remains the production edge limit."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from . import config


@dataclass
class _ClientWindow:
    requests: deque[float]


class InvestigationAdmission:
    def __init__(self) -> None:
        self._clients: dict[str, _ClientWindow] = {}
        self._active = 0
        self._lock = asyncio.Lock()

    async def acquire(self, request: Request) -> "AdmissionLease":
        now = time.monotonic()
        client = config.request_client_key(request)
        async with self._lock:
            window = self._clients.setdefault(client, _ClientWindow(deque()))
            threshold = now - config.INVESTIGATION_RATE_WINDOW_SECONDS
            while window.requests and window.requests[0] <= threshold:
                window.requests.popleft()
            if len(window.requests) >= config.INVESTIGATION_RATE_LIMIT:
                retry_after = max(1, int(window.requests[0] + config.INVESTIGATION_RATE_WINDOW_SECONDS - now) + 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Investigation request limit reached. Try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            if self._active >= config.INVESTIGATION_CONCURRENCY_LIMIT:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="CityScope is at capacity. Try again shortly.",
                    headers={"Retry-After": "5"},
                )
            window.requests.append(now)
            self._active += 1
        return AdmissionLease(self)

    async def release(self) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)

    def reset(self) -> None:
        self._clients.clear()
        self._active = 0


class AdmissionLease:
    def __init__(self, admission: InvestigationAdmission) -> None:
        self._admission = admission

    async def __aenter__(self) -> "AdmissionLease":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._admission.release()


admission = InvestigationAdmission()
