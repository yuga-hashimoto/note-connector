"""Additional MCP tools for ChatGPT connector."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP

from note_mcp.api.articles import create_draft, list_articles
from note_mcp.api.images import insert_image_via_api
from note_mcp.api.public_notes import fetch_public_article, search_public_notes
from note_mcp.auth.session import SessionManager
from note_mcp.chatgpt.images import materialize_image_input
from note_mcp.chatgpt.widgets import (
    ARTICLE_PANEL_URI,
    HOME_URI,
    widget_tool_meta,
)
from note_mcp.models import ArticleInput, ArticleStatus, NoteAPIError


def register_chatgpt_tools(mcp: FastMCP, session_manager: SessionManager) -> None:
    """Register ChatGPT-specific tools and widget resources."""

    @mcp.tool(
        meta=widget_tool_meta(HOME_URI, "note-connector を開いています…", "note-connector"),
        annotations={"readOnlyHint": True},
    )
    async def note_ui_status() -> dict[str, object]:
        """ChatGPT用: 認証状態とクイック情報を返します（Apps SDK ウィジェット用 dict）。"""
        if not session_manager.has_session():
            return {"authenticated": False, "message": "note_login を実行してください"}
        session = session_manager.load()
        if session is None or session.is_expired():
            return {"authenticated": False, "message": "セッションが無効です。note_login を実行してください"}
        return {
            "authenticated": True,
            "message": f"ユーザー: {session.username}",
            "username": session.username,
        }

    @mcp.tool(
        meta=widget_tool_meta(ARTICLE_PANEL_URI, "記事一覧を取得中…", "記事一覧"),
        annotations={"readOnlyHint": True},
    )
    async def note_ui_list_articles(
        status: Annotated[str | None, "draft/published/all"] = None,
        page: Annotated[int, "ページ番号"] = 1,
        limit: Annotated[int, "1ページあたり件数"] = 10,
    ) -> dict[str, object]:
        """ChatGPT用: 記事一覧をウィジェット表示用 dict で返します。"""
        session = session_manager.load()
        if session is None or session.is_expired():
            return {"articles": [], "error": "未認証。note_login を実行してください", "authenticated": False}

        status_filter: ArticleStatus | None = None
        if status is not None and status != "all":
            status_filter = ArticleStatus(status)

        try:
            result = await list_articles(session, status=status_filter, page=page, limit=limit)
        except NoteAPIError as exc:
            return {"articles": [], "error": str(exc), "authenticated": True}

        articles: list[dict[str, Any]] = []
        for article in result.articles:
            articles.append(
                {
                    "id": article.id,
                    "key": article.key,
                    "title": article.title,
                    "status": article.status.value,
                }
            )
        return {
            "articles": articles,
            "total": result.total,
            "page": result.page,
            "has_more": result.has_more,
            "authenticated": True,
        }

    @mcp.tool()
    async def note_attach_image(
        article_key: Annotated[str, "記事キー（n... 形式）"],
        mime_type: Annotated[str, "image/png など"],
        image_base64: Annotated[str | None, "Base64画像データ"] = None,
        image_url: Annotated[str | None, "画像URL"] = None,
        caption: Annotated[str | None, "キャプション"] = None,
    ) -> str:
        """ChatGPT生成画像を記事に挿入します（base64 または URL）。"""
        session = session_manager.load()
        if session is None or session.is_expired():
            return "セッションが無効です。note_loginでログインしてください。"

        work_dir = Path(os.environ.get("NOTE_CONNECTOR_WORK_DIR", "/tmp/note-connector"))
        try:
            file_path = await materialize_image_input(
                work_dir,
                image_base64=image_base64,
                image_url=image_url,
                mime_type=mime_type,
            )
            result = await insert_image_via_api(
                session=session,
                article_id=article_key,
                file_path=str(file_path),
                caption=caption,
            )
        except (ValueError, NoteAPIError, OSError) as exc:
            return f"画像挿入に失敗しました: {exc}"

        return f"画像を挿入しました。記事キー: {result['article_key']}\n画像URL: {result['image_url']}"

    @mcp.tool()
    async def note_create_draft_with_images(
        title: Annotated[str, "記事タイトル"],
        body: Annotated[str, "本文（Markdown）"],
        tags: Annotated[list[str] | None, "タグ"] = None,
        images: Annotated[
            list[dict[str, str]] | None,
            "画像配列。各要素: mime_type, image_base64 または image_url",
        ] = None,
    ) -> str:
        """下書き作成後、ChatGPT画像を本文に挿入します。"""
        session = session_manager.load()
        if session is None or session.is_expired():
            return "セッションが無効です。note_loginでログインしてください。"

        article_input = ArticleInput(title=title, body=body, tags=tags or [])
        try:
            article = await create_draft(session, article_input)
        except NoteAPIError as exc:
            return f"下書き作成に失敗しました: {exc}"

        inserted = 0
        errors: list[str] = []
        work_dir = Path(os.environ.get("NOTE_CONNECTOR_WORK_DIR", "/tmp/note-connector"))
        for index, image_spec in enumerate(images or []):
            mime = image_spec.get("mime_type", "image/png")
            b64 = image_spec.get("image_base64")
            url = image_spec.get("image_url")
            caption = image_spec.get("caption")
            try:
                file_path = await materialize_image_input(
                    work_dir,
                    image_base64=b64,
                    image_url=url,
                    mime_type=mime,
                )
                await insert_image_via_api(
                    session=session,
                    article_id=article.key,
                    file_path=str(file_path),
                    caption=caption,
                )
                inserted += 1
            except (ValueError, NoteAPIError, OSError) as exc:
                errors.append(f"image[{index}]: {exc}")

        lines = [
            f"下書きを作成しました。ID: {article.id}、キー: {article.key}",
            f"挿入した画像: {inserted}件",
        ]
        if errors:
            lines.append("画像エラー:")
            lines.extend(f"  - {e}" for e in errors)
        return "\n".join(lines)

    @mcp.tool(annotations={"readOnlyHint": True})
    async def note_search_public_articles(
        query: Annotated[str, "検索キーワード"],
        size: Annotated[int, "件数（1〜20）"] = 10,
    ) -> dict[str, object]:
        """note.com 上の公開記事をキーワード検索します（ログイン不要）。"""
        try:
            result = await search_public_notes(query, size=size)
        except NoteAPIError as exc:
            return {"items": [], "error": str(exc), "query": query}
        return {
            "query": result.query,
            "is_last_page": result.is_last_page,
            "items": [item.model_dump() for item in result.items],
        }

    @mcp.tool(annotations={"readOnlyHint": True})
    async def note_fetch_public_article(
        note_key_or_url: Annotated[str, "記事キー（n...）または公開URL"],
    ) -> dict[str, object]:
        """他人の公開記事を取得します（ログイン不要）。"""
        try:
            article = await fetch_public_article(note_key_or_url)
        except NoteAPIError as exc:
            return {"error": str(exc)}
        return article.model_dump()

