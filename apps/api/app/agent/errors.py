"""Stable internal error taxonomy for external provider adapters."""

from __future__ import annotations


class ProviderUnavailableError(RuntimeError):
    def __init__(self, provider: str, message: str = "provider unavailable") -> None:
        super().__init__(message)
        self.provider = provider


class ProviderPayloadError(ProviderUnavailableError):
    """Provider responded, but the payload failed the adapter contract."""
