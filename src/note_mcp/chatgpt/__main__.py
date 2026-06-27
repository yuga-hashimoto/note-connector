"""HTTP entrypoint for note-connector ChatGPT connector."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn
from starlette.requests import Request
from starlette.responses import Response

from note_mcp.chatgpt.auth import load_or_create_token
from note_mcp.chatgpt.middleware import ConnectorAuthMiddleware
from note_mcp.chatgpt.tools import register_chatgpt_tools
from note_mcp.chatgpt.widgets import register_chatgpt_resources
from note_mcp.server import _session_manager, mcp


def _default_config_dir() -> Path:
    return Path(os.environ.get("NOTE_CONNECTOR_CONFIG_DIR", Path.home() / ".note-connector"))


def _configure_mcp_allowed_hosts(host_header: str | None) -> None:
    if host_header:
        os.environ.setdefault("MCP_ALLOWED_HOSTS", host_header)
        os.environ.setdefault("MCP_ALLOWED_ORIGINS", f"https://{host_header}")


def build_http_app(token: str) -> ConnectorAuthMiddleware:
    register_chatgpt_tools(mcp, _session_manager)
    register_chatgpt_resources(mcp)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> Response:
        from starlette.responses import JSONResponse

        return JSONResponse({"status": "ok", "app": "note-connector"})

    app = mcp.http_app(path="/mcp", transport="streamable-http", stateless_http=True)
    return ConnectorAuthMiddleware(app, token)


def main() -> None:
    parser = argparse.ArgumentParser(description="note-connector ChatGPT HTTP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--token-file", type=Path, default=None)
    args = parser.parse_args()

    config_dir = _default_config_dir()
    token_path = args.token_file or (config_dir / "token")
    token = os.environ.get("NOTE_CONNECTOR_TOKEN") or load_or_create_token(token_path)

    tunnel_host = os.environ.get("NOTE_CONNECTOR_TUNNEL_HOST")
    _configure_mcp_allowed_hosts(tunnel_host)

    app = build_http_app(token)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
