# note-connector

**note.com** 用 MCP サーバー。ChatGPT **Connector**（Apps SDK UI）と、Claude Code 等の **stdio MCP** の両方に対応します。

⚠️ 非公式 API — [DISCLAIMER.md](DISCLAIMER.md)

---

## ChatGPT で使う（推奨）

### 前提

| 必要なもの | 用途 |
|------------|------|
| **Node.js 20+** | `note-connector` CLI（npm） |
| **[uv](https://docs.astral.sh/uv/)** + **Python 3.13+** | MCP サーバー本体 |
| **Playwright Chromium** | `note_login`（初回のみ） |
| **Tailscale** または **ngrok**（任意） | ChatGPT から届く **固定 Public URL** |

```bash
uv sync
uv run playwright install chromium
```

### CLI のグローバルインストール

```bash
npm install -g note-connector
note-connector update
```

開発中にリポジトリから直接使う場合: `cd chatgpt && npm link`

確認:

```bash
which note-connector
note-connector --version
npm list -g note-connector
```

npm パッケージは **CLI のみ** です。MCP 本体は clone したリポジトリが必要です:

```bash
git clone https://github.com/drillan/note-mcp.git
cd note-mcp && uv sync && uv run playwright install chromium
note-connector config set repoPath "$(pwd)"
```

### 起動

```bash
note-connector
```

- 設定・トークンは自動（`~/.note-connector`）
- **バックグラウンド常駐**（ターミナルは閉じてよい）
- Public MCP URL をコピー、手順は `~/.note-connector/CONNECTOR-SETUP.md`
- ChatGPT 初回接続を最大 **600 秒**待機

```bash
note-connector status
note-connector stop
note-connector --foreground   # デバッグ用
```

ログ: `~/.note-connector/logs/note-connector.log`

### ChatGPT 登録

[docs/guide/chatgpt-connector.md](docs/guide/chatgpt-connector.md) / [Developer mode](https://platform.openai.com/docs/guides/developer-mode)

1. [高度な設定](https://chatgpt.com/#settings/Connectors/Advanced) → **開発者モード ON**
2. [アプリとコネクタ](https://chatgpt.com/#settings/Connectors) → **アプリを作成**
3. 名前 `note-connector` / URL（Public MCP）/ 認証 **なし**
4. チャットで開発者モード → `note-connector` を有効化

### ツール（抜粋）

`note_ui_status`, `note_ui_list_articles`, `note_attach_image`, `note_create_draft_with_images`, `note_create_draft`, `note_publish_article` など

### 固定 URL

```bash
note-connector config set tunnel.domain your-machine.your-tailnet.ts.net
```

---

## グローバル化の整理

| 方式 | いま | 説明 |
|------|------|------|
| `npm install -g note-connector` | ✅ **公開済み** [npm](https://www.npmjs.com/package/note-connector) v0.1.0 |
| `repoPath` | 必須設定 | clone 先を `note-connector config set repoPath ...` |
| MCP 本体 | `uv run` | 上記リポジトリ内の Python |

---

## 開発

- [リリース](docs/development/release.md)
- Python: `uv run pytest` / `ruff` / `mypy`
- npm: `cd chatgpt && npm test`

---

## stdio MCP（Claude Code 等）

```json
{
  "mcpServers": {
    "note-mcp": {
      "command": "uv",
      "args": ["run", "python", "-m", "note_mcp"],
      "cwd": "/path/to/note-connector"
    }
  }
}
```

[docs/quickstart.md](docs/quickstart.md) — 記事作成・公開・画像・埋め込み・プレビューなど
