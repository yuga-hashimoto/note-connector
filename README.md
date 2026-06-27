# note-connector

**ChatGPT 用**の [note.com](https://note.com) **Connector**（MCP + Apps SDK UI）。  
下書き作成・公開・画像挿入・**他人の公開記事の検索・取得**まで、ChatGPT の開発者モードから使えます。

⚠️ **非公式** — note.com とは無関係です。[DISCLAIMER.md](DISCLAIMER.md)

---

## クイックスタート

```bash
npm install -g note-connector
note-connector
```

**これだけで OK です。** 初回の `note-connector`（または `note-connector start`）で次を自動実行します。

| 自動セットアップ | 内容 |
|------------------|------|
| **uv** | 未インストールならインストール |
| **リポジトリ** | `~/.note-connector/repo` に clone（Python MCP 本体） |
| **Python 依存** | `uv sync` |
| **Playwright** | Chromium（`note_login` 用） |
| **設定** | `~/.note-connector`（トークン・トンネル設定） |

手動で clone 済みの場合:

```bash
note-connector config set repoPath /path/to/note-connector
```

### 起動後

- **Public MCP URL** をクリップボードにコピー
- 手順: `~/.note-connector/CONNECTOR-SETUP.md`
- ChatGPT からの初回接続を最大 **600 秒**待機 → 成功したらターミナルは閉じてよい
- バックグラウンド常駐: `note-connector status` / `note-connector stop`

```bash
note-connector --no-open          # ブラウザを開かない
note-connector --no-tunnel        # ローカルのみ（ChatGPT には Public URL が必要）
note-connector --foreground     # デバッグ（ターミナル開きっぱなし）
```

---

## ChatGPT への登録

[Developer mode](https://platform.openai.com/docs/guides/developer-mode) に従います。詳細: [docs/guide/chatgpt-connector.md](docs/guide/chatgpt-connector.md)

1. [高度な設定](https://chatgpt.com/#settings/Connectors/Advanced) → **開発者モード ON**
2. [アプリとコネクタ](https://chatgpt.com/#settings/Connectors) → **「アプリを作成」**
3. **名前** `note-connector` / **接続 URL**（起動時の Public MCP）/ **認証** **なし**
4. 新規チャット → **開発者モード** → `note-connector` を有効化

### 固定 URL（推奨）

```bash
note-connector config set tunnel.domain your-machine.your-tailnet.ts.net
note-connector stop && note-connector
```

Tailscale Funnel または [ngrok 固定ドメイン](docs/development/release.md) を利用できます。

---

## 主な MCP ツール

| ツール | 説明 |
|--------|------|
| `note_login` / `note_check_auth` | note.com ログイン・認証確認 |
| `note_create_draft` / `note_publish_article` | 下書き・公開 |
| `note_attach_image` / `note_create_draft_with_images` | ChatGPT 生成画像の投稿 |
| `note_ui_status` / `note_ui_list_articles` | Apps SDK ウィジェット |
| `note_search_public_articles` | **他人の公開記事**をキーワード検索 |
| `note_fetch_public_article` | 公開 URL またはキーで記事取得 |

---

## 開発者向け

- Python: `uv sync` / `uv run pytest` / `uv run ruff check .`
- npm CLI: `cd chatgpt && npm test`
- リリース: [docs/development/release.md](docs/development/release.md)

## ライセンス

MIT
