"""Tests for public note.com article fetch and search."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from note_mcp.api.public_notes import (
    extract_note_key_from_url,
    fetch_public_article,
    search_public_notes,
)
from note_mcp.models import ErrorCode, NoteAPIError


class TestExtractNoteKeyFromUrl:
    def test_standard_url(self) -> None:
        assert extract_note_key_from_url("https://note.com/drillan/n/n7379c02632c9") == "n7379c02632c9"

    def test_invalid_url(self) -> None:
        with pytest.raises(NoteAPIError) as exc:
            extract_note_key_from_url("https://example.com/foo")
        assert exc.value.code == ErrorCode.INVALID_INPUT


@pytest.mark.asyncio
class TestFetchPublicArticle:
    async def test_fetch_by_key(self) -> None:
        mock_response = {
            "data": {
                "id": 1,
                "key": "nabc",
                "name": "公開タイトル",
                "body": "<p>本文</p>",
                "status": "published",
                "user": {"urlname": "author", "nickname": "著者"},
            }
        }
        with patch("note_mcp.api.public_notes.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_client.get = AsyncMock(return_value=mock_resp)

            article = await fetch_public_article("nabc")

        assert article.key == "nabc"
        assert article.title == "公開タイトル"
        assert article.author_username == "author"
        assert "本文" in article.body_markdown


@pytest.mark.asyncio
class TestSearchPublicNotes:
    async def test_search_returns_hits(self) -> None:
        mock_response = {
            "data": {
                "notes": {
                    "contents": [
                        {
                            "key": "n111",
                            "name": "ヒット1",
                            "user": {"urlname": "u1", "nickname": "U1"},
                            "publish_at": "2026-01-01T00:00:00.000+09:00",
                        }
                    ],
                    "is_last_page": True,
                }
            }
        }
        with patch("note_mcp.api.public_notes.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_client.get = AsyncMock(return_value=mock_resp)

            result = await search_public_notes("python", size=5)

        assert len(result.items) == 1
        assert result.items[0].key == "n111"
        assert result.items[0].url == "https://note.com/u1/n/n111"
