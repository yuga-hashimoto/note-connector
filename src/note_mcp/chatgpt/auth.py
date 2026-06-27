"""Authentication helpers for the ChatGPT HTTP connector."""

from __future__ import annotations

import secrets
from pathlib import Path

from starlette.requests import Request


def extract_bearer_token(request: Request) -> str | None:
    """Extract auth token from Authorization header or ``?key=`` query."""
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    key = request.query_params.get("key")
    if key:
        return key.strip()
    header_key = request.headers.get("x-note-connector-token")
    if header_key:
        return header_key.strip()
    return None


def is_authorized(request: Request, expected_token: str) -> bool:
    """Return whether the request may access protected routes."""
    if request.url.path in ("/healthz", "/health"):
        return True
    if request.url.path.startswith("/assets/"):
        return True
    token = extract_bearer_token(request)
    if token is None:
        return False
    return secrets.compare_digest(token, expected_token)


def load_or_create_token(token_path: Path) -> str:
    """Load persisted connector token or create a new one."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    if token_path.is_file():
        stored = token_path.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    token = secrets.token_urlsafe(32)
    token_path.write_text(token, encoding="utf-8")
    return token


def build_mcp_endpoint_url(public_base: str, token: str) -> str:
    """Build the ChatGPT connector URL."""
    base = public_base.rstrip("/")
    return f"{base}/mcp?key={token}"
