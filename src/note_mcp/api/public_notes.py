"""Fetch and search public note.com articles (no login required)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from note_mcp.models import ErrorCode, NoteAPIError, PublicArticle, PublicArticleSummary, PublicSearchResult
from note_mcp.utils.html_to_markdown import html_to_markdown

NOTE_API_BASE = "https://note.com/api"
USER_AGENT = "Mozilla/5.0 (compatible; note-connector/1.0)"
NOTE_URL_PATTERN = re.compile(r"^https?://(?:www\.)?note\.com/(?P<user>[a-zA-Z0-9_-]+)/n/(?P<key>n[a-z0-9]+)/?$")
NOTE_KEY_PATTERN = re.compile(r"^n[a-z0-9]+$")


def extract_note_key_from_url(url: str) -> str:
    """Extract article key from a public note.com URL."""
    match = NOTE_URL_PATTERN.match(url.strip())
    if not match:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message=f"Invalid note.com article URL: {url}",
            details={"url": url},
        )
    return match.group("key")


def _normalize_key(note_key_or_url: str) -> str:
    text = note_key_or_url.strip()
    if text.startswith("http"):
        return extract_note_key_from_url(text)
    if NOTE_KEY_PATTERN.match(text):
        return text
    raise NoteAPIError(
        code=ErrorCode.INVALID_INPUT,
        message="Provide note key (n...) or https://note.com/user/n/n... URL",
        details={"input": note_key_or_url},
    )


def _public_article_url(username: str, key: str) -> str:
    return f"https://note.com/{username}/n/{key}"


async def fetch_public_article(note_key_or_url: str) -> PublicArticle:
    """Fetch a published article by key or public URL."""
    key = _normalize_key(note_key_or_url)
    url = f"{NOTE_API_BASE}/v3/notes/{key}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    if response.status_code == 404:
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message=f"Article not found or not public: {key}",
            details={"key": key},
        )
    if response.status_code != 200:
        raise NoteAPIError(
            code=ErrorCode.API_ERROR,
            message=f"Failed to fetch public article: HTTP {response.status_code}",
            details={"key": key, "status": response.status_code},
        )
    payload: dict[str, Any] = response.json()
    data_raw = payload.get("data")
    if not isinstance(data_raw, dict):
        data: dict[str, Any] = {}
    else:
        data = data_raw
    if not data:
        raise NoteAPIError(
            code=ErrorCode.API_ERROR,
            message="Invalid API response for public article",
            details={"key": key},
        )
    user_raw = data.get("user")
    user: dict[str, Any] = user_raw if isinstance(user_raw, dict) else {}
    username = str(user.get("urlname") or "")
    if not username:
        raise NoteAPIError(
            code=ErrorCode.API_ERROR,
            message="Public article response missing author urlname",
            details={"key": key},
        )
    body_html = str(data.get("body") or "")
    return PublicArticle(
        key=str(data.get("key") or key),
        title=str(data.get("name") or ""),
        body_markdown=html_to_markdown(body_html),
        author_username=username,
        author_nickname=str(user.get("nickname")) if user.get("nickname") else None,
        url=_public_article_url(username, str(data.get("key") or key)),
        status=str(data.get("status") or "published"),
    )


async def search_public_notes(query: str, *, size: int = 10) -> PublicSearchResult:
    """Search published notes on note.com."""
    if not query.strip():
        raise NoteAPIError(
            code=ErrorCode.INVALID_INPUT,
            message="Search query must not be empty",
            details={},
        )
    size_clamped = max(1, min(size, 20))
    url = f"{NOTE_API_BASE}/v3/searches?context=note&q={quote(query)}&size={size_clamped}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    if response.status_code != 200:
        raise NoteAPIError(
            code=ErrorCode.API_ERROR,
            message=f"Search failed: HTTP {response.status_code}",
            details={"query": query, "status": response.status_code},
        )
    payload_search: dict[str, Any] = response.json()
    data_search = payload_search.get("data")
    search_data: dict[str, Any] = data_search if isinstance(data_search, dict) else {}
    notes_block_raw = search_data.get("notes")
    notes_block: dict[str, Any] = notes_block_raw if isinstance(notes_block_raw, dict) else {}
    contents: list[Any] = []
    raw = notes_block.get("contents")
    if isinstance(raw, list):
        contents = raw
    items: list[PublicArticleSummary] = []
    for item in contents:
        if not isinstance(item, dict):
            continue
        user_item_raw = item.get("user")
        user_item: dict[str, Any] = user_item_raw if isinstance(user_item_raw, dict) else {}
        username = str(user_item.get("urlname") or "")
        key = str(item.get("key") or "")
        if not username or not key:
            continue
        items.append(
            PublicArticleSummary(
                key=key,
                title=str(item.get("name") or ""),
                author_username=username,
                author_nickname=str(user_item.get("nickname")) if user_item.get("nickname") else None,
                url=_public_article_url(username, key),
                published_at=str(item.get("publish_at")) if item.get("publish_at") else None,
            )
        )
    is_last = None
    if isinstance(notes_block, dict) and "is_last_page" in notes_block:
        is_last = bool(notes_block.get("is_last_page"))
    return PublicSearchResult(items=items, query=query, is_last_page=is_last)
