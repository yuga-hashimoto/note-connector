"""Contract tests for ChatGPT-specific MCP tools."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from note_mcp.auth.session import SessionManager
from note_mcp.chatgpt.tools import register_chatgpt_tools


@pytest.fixture
def chatgpt_mcp() -> FastMCP:
    server = FastMCP("note-connector-test")
    register_chatgpt_tools(server, SessionManager())
    return server


@pytest.mark.asyncio
async def test_note_ui_status_tool_registered(chatgpt_mcp: FastMCP) -> None:
    tools = await chatgpt_mcp.get_tools()
    assert "note_ui_status" in tools


@pytest.mark.asyncio
async def test_note_create_draft_with_images_tool_registered(chatgpt_mcp: FastMCP) -> None:
    tools = await chatgpt_mcp.get_tools()
    assert "note_create_draft_with_images" in tools


@pytest.mark.asyncio
async def test_note_search_public_articles_tool_registered(chatgpt_mcp: FastMCP) -> None:
    tools = await chatgpt_mcp.get_tools()
    assert "note_search_public_articles" in tools


@pytest.mark.asyncio
async def test_note_fetch_public_article_tool_registered(chatgpt_mcp: FastMCP) -> None:
    tools = await chatgpt_mcp.get_tools()
    assert "note_fetch_public_article" in tools
