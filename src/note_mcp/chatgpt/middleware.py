"""ASGI middleware for connector authentication."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from note_mcp.chatgpt.access_log import record_mcp_access
from note_mcp.chatgpt.auth import is_authorized


class ConnectorAuthMiddleware:
    """Reject unauthorized requests to MCP endpoints."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        if not is_authorized(request, self.token):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        if request.method == "POST" and request.url.path.startswith("/mcp"):
            record_mcp_access(request.client.host if request.client else None)
        await self.app(scope, receive, send)
