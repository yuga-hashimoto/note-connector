"""Apps SDK HTML widgets for note-connector."""

from __future__ import annotations

HOME_URI = "ui://note-connector/home-v1.html"
ARTICLE_PANEL_URI = "ui://note-connector/article-panel-v1.html"

APPS_MIME = "text/html;profile=mcp-app"

WIDGET_RUNTIME = """
function noteConnectorParsePayload(payload) {
  if (!payload || typeof payload !== 'object') return {};
  if (typeof payload.result === 'string') {
    try { var inner = JSON.parse(payload.result); if (inner && typeof inner === 'object') return inner; } catch (e) {}
  }
  if (payload.data && typeof payload.data === 'object') return payload.data;
  return payload;
}
(function() {
  function boot() {
    const openai = window.openai || {};
    const raw = openai.toolOutput || openai.structuredContent || {};
    const data = noteConnectorParsePayload(raw);
    const callTool = (name, args) => openai.callTool && openai.callTool(name, args);
    const ctx = { data: data, callTool: callTool };
    if (typeof window.NoteConnectorRender === 'function') window.NoteConnectorRender(ctx);
  }
  window.addEventListener('openai:set_globals', boot);
  boot();
})();
"""


def _widget_document(title: str, body: str, render_js: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; }}
    .root {{ padding: 12px; font-size: 13px; }}
    .title {{ font-weight: 600; margin-bottom: 8px; }}
    .mono {{ font-family: ui-monospace, monospace; white-space: pre-wrap; }}
    .muted {{ color: #666; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 10px; margin: 8px 0; }}
  </style>
</head>
<body>
  <div id="root" class="root">{body}</div>
  <script>{render_js}</script>
  <script>{WIDGET_RUNTIME}</script>
</body>
</html>"""


def home_widget_html() -> str:
    render = """
window.NoteConnectorRender = function(ctx) {
  const root = document.getElementById('root');
  const d = ctx.data || {};
  root.innerHTML = '<div class="title">note-connector</div>'
    + '<div class="muted">ChatGPT connector for note.com</div>'
    + '<div class="card"><div>認証: ' + (d.authenticated ? 'OK' : '未ログイン') + '</div>'
    + '<div class="small">' + (d.message || '') + '</div></div>';
};
"""
    return _widget_document("note-connector Home", '<div class="muted">Loading…</div>', render)


def article_panel_widget_html() -> str:
    render = """
window.NoteConnectorRender = function(ctx) {
  const root = document.getElementById('root');
  const d = ctx.data || {};
  const articles = d.articles || [];
  if (!articles.length) {
    root.innerHTML = '<div class="muted">記事がありません</div>';
    return;
  }
  root.innerHTML = '<div class="title">記事一覧 (' + articles.length + ')</div>'
    + articles.map(function(a) {
      return '<div class="card"><strong>' + (a.title || '') + '</strong><br/>'
        + '<span class="mono">' + (a.id || '') + ' / ' + (a.key || '') + '</span><br/>'
        + '<span class="muted">' + (a.status || '') + '</span></div>';
    }).join('');
};
"""
    return _widget_document("note-connector Articles", '<div class="muted">Loading…</div>', render)


def widget_tool_meta(uri: str, invoking: str, invoked: str) -> dict[str, object]:
    return {
        "ui": {"resourceUri": uri},
        "openai/outputTemplate": uri,
        "openai/toolInvocation/invoking": invoking,
        "openai/toolInvocation/invoked": invoked,
        "openai/widgetAccessible": True,
    }


def register_chatgpt_resources(mcp: object) -> None:
    """Register widget HTML as MCP resources."""
    from fastmcp import FastMCP

    server = mcp
    if not isinstance(server, FastMCP):
        return

    @server.resource(HOME_URI, mime_type=APPS_MIME, meta={"openai/widgetDescription": "note-connector home"})
    def note_home_resource() -> str:
        return home_widget_html()

    @server.resource(
        ARTICLE_PANEL_URI,
        mime_type=APPS_MIME,
        meta={"openai/widgetDescription": "note.com article list"},
    )
    def note_article_panel_resource() -> str:
        return article_panel_widget_html()
