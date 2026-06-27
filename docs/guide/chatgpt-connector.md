# ChatGPT Connector（note-connector）

## クイックスタート

```bash
npm install -g note-connector
note-connector
```

起動ログの **Public MCP URL** と `~/.note-connector/CONNECTOR-SETUP.md` を参照してください。

## ChatGPT 側の手順（必須）

OpenAI [Developer mode](https://platform.openai.com/docs/guides/developer-mode) に従います。

1. [ChatGPT → アプリとコネクタ](https://chatgpt.com/#settings/Connectors)
2. [高度な設定](https://chatgpt.com/#settings/Connectors/Advanced) → **開発者モード ON**
3. アプリとコネクタに戻り **「アプリを作成」**（Developer mode ON 時のみ表示）
4. フォーム:
   - **名前**: `note-connector`
   - **接続 URL**: ターミナルに表示された `https://.../mcp?key=...`
   - **認証**: **なし**（No authentication）
5. 新しいチャット → **開発者モード** → `note-connector` を有効化

## note.com

初回は `note_login`（Playwright）が必要です。`note-connector` 起動時にブラウザが開きます。

## ツール

ChatGPT 専用: `note_ui_status`, `note_ui_list_articles`, `note_attach_image`, `note_create_draft_with_images` ほか従来の `note_*` 一式。
