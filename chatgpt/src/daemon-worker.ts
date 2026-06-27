/**
 * Background worker: MCP + tunnel. Started detached by `note-connector`.
 */
import fs from "node:fs";
import path from "node:path";
import { buildMcpEndpoint, loadConfig, loadOrCreateToken } from "./config.js";
import { configDir } from "./paths.js";
import { startPythonServer } from "./spawn-python.js";
import { resolveGatewayPort } from "./net.js";
import { discoverTailscaleFqdn } from "./tunnel/tailscale.js";
import { isNoteAuthenticated, startNoteLoginInBackground } from "./note-auth.js";
import { TunnelManager } from "./tunnel/manager.js";
import { saveRuntime, cliPidPath, loadLastMcpAccess } from "./daemon-state.js";
import { ensureInitialized, type StartOptions } from "./runtime.js";

async function verifyHealth(port: number): Promise<boolean> {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/healthz`, { signal: AbortSignal.timeout(5000) });
    return res.ok;
  } catch {
    return false;
  }
}

function watchFirstChatGptAccess(sinceIso: string, logFile: string): void {
  let announced = false;
  const tick = () => {
    if (announced) return;
    const rec = loadLastMcpAccess();
    if (rec && rec.at > sinceIso) {
      announced = true;
      const line = `\n✓ ChatGPT から MCP 接続を確認しました (${rec.at})\n`;
      fs.appendFileSync(logFile, line);
      process.stdout.write(line);
    }
  };
  setInterval(tick, 2000);
}

export async function runDaemonWorker(opts: StartOptions, logFile: string): Promise<void> {
  await ensureInitialized();
  const startedAt = new Date().toISOString();
  fs.writeFileSync(cliPidPath(), String(process.pid));

  const config = loadConfig();
  const port = await resolveGatewayPort(opts.port ?? config.gatewayPort, "127.0.0.1");
  const tokenFile = path.join(configDir(), "token");
  const token = loadOrCreateToken();

  const tunnel = new TunnelManager();
  const tunnelHostHint =
    config.tunnel.domain ?? (config.tunnel.publicUrl ? new URL(config.tunnel.publicUrl).host : undefined);

  const child = startPythonServer({
    host: "127.0.0.1",
    port,
    tokenFile,
    tunnelHost: tunnelHostHint,
  });

  for (let i = 0; i < 60; i++) {
    if (await verifyHealth(port)) break;
    await new Promise((r) => setTimeout(r, 500));
  }

  if (!opts.noTunnel) {
    await tunnel.start(port, config.tunnel);
  }

  const t = tunnel.current();
  const localUrl = buildMcpEndpoint(`http://127.0.0.1:${port}`, token);
  const publicUrl = t.url ? buildMcpEndpoint(t.url, token) : localUrl;

  saveRuntime({
    cliPid: process.pid,
    port,
    publicMcpUrl: publicUrl,
    localMcpUrl: localUrl,
    startedAt,
    logFile,
    tunnelProvider: t.provider,
  });

  if (!isNoteAuthenticated() && !opts.skipNoteLogin) {
    startNoteLoginInBackground();
  }

  watchFirstChatGptAccess(startedAt, logFile);

  child.on("exit", (code) => {
    if (code !== 0 && code !== null) {
      fs.appendFileSync(logFile, `\nPython MCP exited: ${code}\n`);
      process.exit(code ?? 1);
    }
  });

  const shutdown = () => {
    tunnel.stop();
    child.kill("SIGTERM");
    try {
      fs.rmSync(cliPidPath(), { force: true });
    } catch {
      /* ignore */
    }
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  await new Promise(() => {});
}

const logFile = process.env.NOTE_CONNECTOR_LOG_FILE;
if (logFile && process.env.NOTE_CONNECTOR_DAEMON_WORKER === "1") {
  const opts: StartOptions = {
    noTunnel: process.env.NOTE_CONNECTOR_NO_TUNNEL === "1",
    skipNoteLogin: process.env.NOTE_CONNECTOR_SKIP_NOTE_LOGIN === "1",
    port: process.env.NOTE_CONNECTOR_PORT ? parseInt(process.env.NOTE_CONNECTOR_PORT, 10) : undefined,
  };
  runDaemonWorker(opts, logFile).catch((e) => {
    fs.appendFileSync(logFile, `\n${(e as Error).stack ?? e}\n`);
    process.exit(1);
  });
}
