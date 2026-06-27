import fs from "node:fs";
import path from "node:path";
import { configDir } from "./paths.js";
import {
  CHATGPT_ADVANCED_SETTINGS,
  CHATGPT_APPS_CONNECTORS,
  CONNECTOR_NAME,
  SETUP_STEPS_JA,
  formatSetupGuide,
} from "./chatgpt-setup.js";
import { copyToClipboard, openBrowser } from "./util.js";

const NOTE_LOGIN = "https://note.com/login";

export interface OnboardingInput {
  publicMcpUrl: string;
  localMcpUrl: string;
  noteAuthenticated: boolean;
  tunnelOk: boolean;
  noOpen?: boolean;
  noClipboard?: boolean;
}

export async function runOnboarding(input: OnboardingInput): Promise<void> {
  const { publicMcpUrl, localMcpUrl, noteAuthenticated, tunnelOk, noOpen, noClipboard } = input;

  if (tunnelOk && !noClipboard) {
    const copied = await copyToClipboard(publicMcpUrl);
    if (copied) {
      console.log("✓ Public MCP URL をクリップボードにコピーしました（「接続 URL」に貼り付け）");
    }
  }

  const guidePath = path.join(configDir(), "CONNECTOR-SETUP.md");
  fs.writeFileSync(guidePath, formatSetupGuide(publicMcpUrl), "utf8");
  console.log(`✓ 詳細手順: ${guidePath}`);

  console.log("");
  console.log("══════════════════════════════════════════════════════════");
  console.log("  ChatGPT に note-connector を登録する手順");
  console.log("══════════════════════════════════════════════════════════");
  console.log("");

  if (!tunnelOk) {
    console.log("⚠ トンネル未接続のため Public URL がありません。ChatGPT には使えません。");
    console.log(`  ローカル検証用: ${localMcpUrl}`);
    console.log("");
    return;
  }

  for (const line of SETUP_STEPS_JA) {
    console.log(line);
  }
  console.log("");
  console.log("  接続 URL（貼り付け用）:");
  console.log(`  ${publicMcpUrl}`);
  console.log("");

  if (!noteAuthenticated) {
    console.log("【note.com】ログイン用ブラウザを開きます（MCP セッション保存まで待機）");
  } else {
    console.log("【note.com】ログイン済み ✓");
  }

  console.log("══════════════════════════════════════════════════════════");
  console.log("");

  if (!noOpen) {
    openBrowser(CHATGPT_ADVANCED_SETTINGS);
    console.log("ブラウザ: 高度な設定 → 開発者モードを ON にしてください");
    console.log(`次に: ${CHATGPT_APPS_CONNECTORS} で「アプリを作成」`);
    console.log(`  名前: ${CONNECTOR_NAME} / 認証: なし / URL: クリップボードの内容`);
    if (!noteAuthenticated) {
      setTimeout(() => openBrowser(NOTE_LOGIN), 1500);
    }
  }
}
