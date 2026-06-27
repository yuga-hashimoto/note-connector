"""Tests for ChatGPT connector authentication."""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request

from note_mcp.chatgpt.auth import (
    build_mcp_endpoint_url,
    extract_bearer_token,
    is_authorized,
    load_or_create_token,
)


def test_extract_bearer_token_from_header() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/mcp",
        "headers": [(b"authorization", b"Bearer secret-token")],
    }
    request = Request(scope)
    assert extract_bearer_token(request) == "secret-token"


def test_extract_bearer_token_from_query() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/mcp",
        "query_string": b"key=query-token",
        "headers": [],
    }
    request = Request(scope)
    assert extract_bearer_token(request) == "query-token"


def test_is_authorized_matches_token() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/mcp",
        "headers": [(b"authorization", b"Bearer abc")],
    }
    request = Request(scope)
    assert is_authorized(request, "abc") is True
    assert is_authorized(request, "wrong") is False


def test_is_authorized_allows_healthz_without_token() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/healthz",
        "headers": [],
    }
    request = Request(scope)
    assert is_authorized(request, "abc") is True


def test_build_mcp_endpoint_url() -> None:
    url = build_mcp_endpoint_url("https://example.ts.net/", "tok123")
    assert url == "https://example.ts.net/mcp?key=tok123"


def test_load_or_create_token_persists(tmp_path: Path) -> None:
    token_path = tmp_path / "token"
    first = load_or_create_token(token_path)
    second = load_or_create_token(token_path)
    assert first == second
    assert len(first) >= 32
