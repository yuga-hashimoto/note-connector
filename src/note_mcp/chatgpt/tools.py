"""Additional MCP tools for ChatGPT connector."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from note_mcp.api.articles import create_draft, delete_article, list_articles, unpublish_article
from note_mcp.api.openai_file_images import insert_body_image_from_file_param
from note_mcp.api.public_notes import fetch_public_article, search_public_notes
from note_mcp.auth.session import SessionManager
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

    @mcp.tool(
        meta={
            "openai/fileParams": ["images"],
            "openai/toolInvocation/invoking": "Creating draft with images…",
            "openai/toolInvocation/invoked": "Draft created with images",
        }
    )
    async def note_create_draft_with_images(
        title: Annotated[str, "記事タイトル"],
        body: Annotated[str, "本文（Markdown）"],
        tags: Annotated[list[str] | None, "タグ"] = None,
        images: Annotated[
            list[dict[str, Any]] | None,
            (
                "Apps SDK file referenceの配列。"
                "各要素は file reference object（download_url/file_id必須）。"
                "captionキーでキャプションを指定可。"
            ),
        ] = None,
    ) -> dict[str, Any]:
        """下書きを作成し、Apps SDK file parameterの画像を本文に挿入します。"""
        session = session_manager.load()
        if session is None or session.is_expired():
            return {"ok": False, "error": "セッションが無効です。note_loginでログインしてください。"}

        article_input = ArticleInput(title=title, body=body, tags=tags or [])
        try:
            article = await create_draft(session, article_input)
        except NoteAPIError as exc:
            return {"ok": False, "error": str(exc)}

        inserted = 0
        errors: list[dict[str, Any]] = []
        for index, image_spec in enumerate(images or []):
            caption = image_spec.get("caption")
            try:
                await insert_body_image_from_file_param(
                    session=session,
                    article_id=article.key,
                    image_file=image_spec,
                    caption=caption,
                )
                inserted += 1
            except (ValueError, NoteAPIError) as exc:
                errors.append({"index": index, "error": str(exc)})

        return {
            "ok": True,
            "article_id": article.id,
            "article_key": article.key,
            "inserted": inserted,
            "errors": errors,
        }

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

    @mcp.tool()
    async def note_delete_article(
        article_key: Annotated[str, "削除する記事のキー（例: n1234567890ab）"],
        confirm: Annotated[bool, "削除を実行する場合はTrue、確認のみの場合はFalse"] = False,
    ) -> dict[str, object]:
        """公開記事を含む任意の記事を削除します（下書き・公開問わず削除可、取り消し不可）。"""
        session = session_manager.load()
        if session is None or session.is_expired():
            return {"error": "セッションが無効です。note_loginでログインしてください。"}

        try:
            result = await delete_article(session, article_key, confirm=confirm)
        except NoteAPIError as exc:
            return {"error": str(exc)}

        from note_mcp.models import DeletePreview, DeleteResult

        if isinstance(result, DeletePreview):
            return {
                "action": "preview",
                "article_title": result.article_title,
                "article_key": result.article_key,
                "status": result.status.value,
                "message": result.message,
            }
        elif isinstance(result, DeleteResult):
            return {
                "action": "deleted",
                "success": result.success,
                "article_title": result.article_title,
                "article_key": result.article_key,
                "message": result.message,
            }
        return {"result": str(result)}

    @mcp.tool()
    async def note_unpublish_article(
        article_key: Annotated[str, "下書きに戻す公開記事のキー（例: n1234567890ab）"],
    ) -> dict[str, object]:
        """公開記事を下書きに戻します（記事内容は保持されます）。"""
        session = session_manager.load()
        if session is None or session.is_expired():
            return {"error": "セッションが無効です。note_loginでログインしてください。"}

        try:
            article = await unpublish_article(session, article_key)
        except NoteAPIError as exc:
            return {"error": str(exc)}

        return {
            "unpublished": True,
            "title": article.title,
            "key": article.key,
            "status": "draft",
            "url": article.url,
            "message": f"記事「{article.title}」を下書きに戻しました。",
        }
