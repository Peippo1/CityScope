"""Stable internal error taxonomy for external provider adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx


FailureCategory = Literal[
    "authentication", "permission", "quota_or_rate_limit", "upstream_5xx",
    "transport", "timeout", "invalid_response", "unknown",
]


@dataclass(frozen=True)
class ProviderDiagnostic:
    category: FailureCategory
    http_status: int | None = None
    response_received: bool = False


class ProviderOperationError(RuntimeError):
    """A provider operation returned an MCP-level error response."""

    def __init__(self, provider: str, message: str = "provider operation failed") -> None:
        super().__init__(message)
        self.provider = provider
        self.response_received = True


class ProviderUnavailableError(RuntimeError):
    def __init__(self, provider: str, message: str = "provider unavailable") -> None:
        super().__init__(message)
        self.provider = provider


class ProviderPayloadError(ProviderUnavailableError):
    """Provider responded, but the payload failed the adapter contract."""


def _status_diagnostic(status: int) -> ProviderDiagnostic:
    if not 100 <= status <= 599:
        return ProviderDiagnostic(category="unknown", response_received=True)
    if status == 401:
        category: FailureCategory = "authentication"
    elif status == 403:
        category = "permission"
    elif status == 429:
        category = "quota_or_rate_limit"
    elif 500 <= status <= 599:
        category = "upstream_5xx"
    else:
        category = "unknown"
    return ProviderDiagnostic(category=category, http_status=status, response_received=True)


def _exception_diagnostic(exc: BaseException) -> ProviderDiagnostic:
    if isinstance(exc, httpx.HTTPStatusError):
        return _status_diagnostic(exc.response.status_code)
    if isinstance(exc, ProviderPayloadError):
        return ProviderDiagnostic(category="invalid_response", response_received=True)
    if isinstance(exc, ProviderOperationError):
        return ProviderDiagnostic(category="unknown", response_received=True)
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError, TimeoutError)):
        return ProviderDiagnostic(category="timeout")
    if isinstance(exc, asyncio.CancelledError):
        return ProviderDiagnostic(category="transport")
    if isinstance(exc, httpx.RequestError):
        return ProviderDiagnostic(category="transport")
    if isinstance(exc, BaseExceptionGroup):
        diagnostics = [_exception_diagnostic(child) for child in exc.exceptions]
        priority = {"authentication": 0, "permission": 1, "quota_or_rate_limit": 2, "upstream_5xx": 3, "invalid_response": 4, "timeout": 5, "transport": 6, "unknown": 7}
        return min(diagnostics, key=lambda item: priority[item.category], default=ProviderDiagnostic("unknown"))
    return ProviderDiagnostic(category="unknown")


def classify_provider_exception(exc: BaseException) -> ProviderDiagnostic:
    """Classify failures without exposing exception messages or payloads."""
    try:
        return _exception_diagnostic(exc)
    except BaseException:
        return ProviderDiagnostic(category="unknown")


def contains_cancellation(exc: BaseException) -> bool:
    """Detect direct or nested task cancellation without inspecting messages."""
    if isinstance(exc, asyncio.CancelledError):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(contains_cancellation(child) for child in exc.exceptions)
    return False
