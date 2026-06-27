/** ChatGPT Connector setup URLs and copy (aligned with OpenAI Developer mode docs). */

export const CHATGPT_APPS_CONNECTORS = "https://chatgpt.com/#settings/Connectors";
export const CHATGPT_ADVANCED_SETTINGS = "https://chatgpt.com/#settings/Connectors/Advanced";

export const CONNECTOR_NAME = "note-connector";

export const SETUP_STEPS_JA: readonly string[] = [
  "【準備】ChatGPT の Plus / Pro / Business 等のアカウントで Web 版を開く",
  "【1】設定 → アプリとコネクタ（Apps & Connectors）を開く",
  "【2】高度な設定（Advanced settings）を開く",
  "【3】開発者モード（Developer mode）を ON にする",
  "【4】アプリとコネクタ画面に戻る",
  "【5】「アプリを作成」（Create app）をクリック ※開発者モード ON のときだけ表示",
  "【6】作成フォームに入力して保存:",
  "     ・名前: note-connector",
  "     ・接続 / Connector URL: （下の Public MCP URL を貼り付け）",
  "     ・認証: なし / No authentication（URL に key= が含まれるため）",
  "【7】新しいチャット → ＋メニュー → 開発者モードで note-connector を有効化",
  "【8】例:「note の認証状態を確認して」「下書き一覧を見せて」",
];

export function formatSetupGuide(publicMcpUrl: string): string {
  return `# note-connector — ChatGPT 接続手順

参照: OpenAI [Developer mode](https://platform.openai.com/docs/guides/developer-mode) / LocalAnt 同様の MCP Connector 手順

## Public MCP URL（コピーして貼り付け）

\`\`\`
${publicMcpUrl}
\`\`\`

## 手順（この順番で）

1. **ChatGPT** → [アプリとコネクタ](${CHATGPT_APPS_CONNECTORS})
2. **[高度な設定](${CHATGPT_ADVANCED_SETTINGS})** を開く
3. **開発者モード（Developer mode）** を **ON**
4. 再度 [アプリとコネクタ](${CHATGPT_APPS_CONNECTORS}) へ
5. **「アプリを作成」**（Create app）をクリック  
   （開発者モードが ON のときだけ表示されます）
6. フォーム:
   | 項目 | 入力 |
   |------|------|
   | 名前 | \`${CONNECTOR_NAME}\` |
   | 接続 URL / Connector URL | 上記 Public MCP URL 全体 |
   | 認証 | **なし** / **No authentication** |
7. 保存後、下書き（Drafts）に \`${CONNECTOR_NAME}\` が表示されます
8. **新しいチャット** → ツール／＋メニュー → **開発者モード** → \`${CONNECTOR_NAME}\` を選択
9. 会話で note 操作（初回は \`note_login\` が必要な場合あり）

## 注意

- プロトコル: **Streaming HTTP**（\`/mcp\`）
- 認証は URL の \`?key=\` で行うため、ChatGPT 側は **認証なし** で正しいです
- 書き込みツールは ChatGPT が確認を求めることがあります（Developer mode の仕様）

## note.com

未ログインの場合、別タブで note.com にログインし、Playwright のログインが完了するまで待ってください。
`;
}
