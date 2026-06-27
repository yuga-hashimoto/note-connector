import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ensureConfigDir, configDir } from "./paths.js";
import {
  isDaemonRunning,
  loadRuntime,
  loadLastMcpAccess,
} from "./daemon-state.js";
import { runOnboarding } from "./onboarding.js";
import { isNoteAuthenticated } from "./note-auth.js";
import type { StartOptions } from "./runtime.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function logsDir(): string {
  const dir = path.join(configDir(), "logs");
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function waitForRuntime(timeoutMs: number): Promise<ReturnType<typeof loadRuntime>> {
  return new Promise((resolve) => {
    const start = Date.now();
    const tick = () => {
      const rt = loadRuntime();
      if (rt) {
        resolve(rt);
        return;
      }
      if (Date.now() - start > timeoutMs) {
        resolve(null);
        return;
      }
      setTimeout(tick, 400);
    };
    tick();
  });
}

function waitForChatGptAccess(sinceIso: string, timeoutMs: number): Promise<boolean> {
  return new Promise((resolve) => {
    const start = Date.now();
    const tick = () => {
      const rec = loadLastMcpAccess();
      if (rec && rec.at > sinceIso) {
        resolve(true);
        return;
      }
      if (Date.now() - start > timeoutMs) {
        resolve(false);
        return;
      }
      setTimeout(tick, 1500);
    };
    tick();
  });
}

export async function spawnDaemon(opts: StartOptions): Promise<void> {
  if (isDaemonRunning()) {
    const rt = loadRuntime();
    console.log("note-connector はすでにバックグラウンドで動作中です。");
    if (rt) {
      console.log(`Public MCP: ${rt.publicMcpUrl}`);
      console.log(`ログ: ${rt.logFile}`);
      console.log("停止: note-connector stop / 状態: note-connector status");
    }
    return;
  }

  ensureConfigDir();
  const logFile = path.join(logsDir(), "note-connector.log");
  const worker = path.join(__dirname, "daemon-worker.js");

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    NOTE_CONNECTOR_DAEMON_WORKER: "1",
    NOTE_CONNECTOR_LOG_FILE: logFile,
    NOTE_CONNECTOR_NO_TUNNEL: opts.noTunnel ? "1" : "0",
    NOTE_CONNECTOR_SKIP_NOTE_LOGIN: opts.skipNoteLogin ? "1" : "0",
  };
  if (opts.port) env.NOTE_CONNECTOR_PORT = String(opts.port);

  const out = fs.openSync(logFile, "a");
  const child = spawn(process.execPath, [worker], {
    detached: true,
    stdio: ["ignore", out, out],
    env,
  });
  child.unref();

  console.log("バックグラウンドで起動中…");
  const rt = await waitForRuntime(600_000);
  if (!rt) {
    console.error(`起動タイムアウト。ログ: ${logFile}`);
    process.exit(1);
  }

  console.log("");
  console.log("note-connector をバックグラウンドで起動しました");
  console.log(`PID: ${rt.cliPid}`);
  console.log(`ログ: ${rt.logFile}`);
  console.log(`Local MCP: ${rt.localMcpUrl}`);
  console.log(`Public MCP: ${rt.publicMcpUrl}`);

  const noteOk = isNoteAuthenticated();
  await runOnboarding({
    publicMcpUrl: rt.publicMcpUrl,
    localMcpUrl: rt.localMcpUrl,
    noteAuthenticated: noteOk,
    tunnelOk: rt.publicMcpUrl.startsWith("https://"),
    noOpen: opts.noOpen,
    noClipboard: opts.noClipboard,
  });

  console.log("");
  console.log("ChatGPT からの初回接続を待っています（最大 600 秒）…");
  const connected = await waitForChatGptAccess(rt.startedAt, 600_000);
  if (connected) {
    const rec = loadLastMcpAccess();
    console.log(`✓ ChatGPT 接続成功${rec?.remote ? ` (${rec.remote})` : ""}`);
    console.log("このターミナルは閉じて大丈夫です。サーバーはバックグラウンドで動き続けます。");
  } else {
    console.log("まだ ChatGPT からの接続はありません。");
    console.log("Connector 登録後に ChatGPT で使うと、ログに接続が記録されます。");
    console.log("確認: note-connector status");
  }
  console.log("");
  console.log("停止: note-connector stop");
}
