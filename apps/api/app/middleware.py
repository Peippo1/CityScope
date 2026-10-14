from __future__ import annotations

import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import config
from .observability import emit_event, elapsed_ms, new_request_id, reset_request_context, set_request_context


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Cache-Control": "no-store",
}


class SecurityBoundaryMiddleware:
    """Apply inexpensive request and response protections before route handling."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        request_id = new_request_id(headers.get(b"x-request-id", b"").decode("ascii", errors="ignore"))
        tokens = set_request_context(request_id)
        try:
            await self._call(scope, receive, send, headers, request_id, started)
        finally:
            reset_request_context(tokens)

    async def _call(self, scope: Scope, receive: Receive, send: Send, headers: dict[bytes, bytes], request_id: str, started: float) -> None:
        status_code = 500
        raw_length = headers.get(b"content-length")
        if raw_length:
            try:
                too_large = int(raw_length) > config.MAX_REQUEST_BYTES
            except ValueError:
                too_large = True
            if too_large:
                response = JSONResponse({"detail": "Request payload is too large."}, status_code=413)
                response.headers.update(SECURITY_HEADERS)
                response.headers["X-Request-ID"] = request_id
                await response(scope, receive, send)
                emit_event("request.completed", method=scope.get("method"), path=scope.get("path"), status_code=413, duration_ms=elapsed_ms(started))
                return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                nonlocal status_code
                status_code = int(message.get("status", 500))
                response_headers = list(message.get("headers", []))
                response_headers.extend((key.lower().encode(), value.encode()) for key, value in SECURITY_HEADERS.items())
                response_headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": response_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            emit_event("request.completed", method=scope.get("method"), path=scope.get("path"), status_code=status_code, duration_ms=elapsed_ms(started))
