import fs from "node:fs";
import path from "node:path";
import { buildMcpEndpoint, loadConfig, loadOrCreateToken, saveConfig } from "./config.js";
import { configDir } from "./paths.js";
import { startPythonServer } from "./spawn-python.js";
import { resolveGatewayPort } from "./net.js";
import { discoverTailscaleFqdn } from "./tunnel/tailscale.js";
import { runOnboarding } from "./onboarding.js";
import { isNoteAuthenticated, startNoteLoginInBackground } from "./note-auth.js";
import { spawnDaemon } from "./daemon.js";
import { setupDependencies } from "./setup-dependencies.js";
import { TunnelManager } from "./tunnel/manager.js";

export interface StartOptions {
  noTunnel?: boolean;
  port?: number;
  noOpen?: boolean;
  noClipboard?: boolean;
  skipNoteLogin?: boolean;
}

async function verifyHealth(port: number): Promise<boolean> {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/healthz`, { signal: AbortSignal.timeout(5000) });
    return res.ok;
  } catch {
    return false;
  }
}

/** @deprecated Use `note-connector` or `note-connector start` */
export async function runSetup(): Promise<void> {
  console.log("Setup is included in start. Just run: note-connector");
}

export async function runStart(opts: StartOptions): Promise<void> {
  console.log("note-connector — ChatGPT Connector セットアップ中…");
  const report = await setupDependencies();
  for (const w of report.warnings) {
    console.warn(`⚠ ${w}`);
  }
  loadOrCreateToken();
  const fqdn = discoverTailscaleFqdn();
  if (fqdn) {
    const config = loadConfig();
    if (!config.tunnel.domain) {
      saveConfig({ ...config, tunnel: { ...config.tunnel, domain: fqdn } });
      console.log(`Tailscale FQDN: ${fqdn}`);
    }
  }
  console.log("依存関係の準備が完了しました。");
  await spawnDaemon(opts);
}

/** Foreground mode (debug): keep terminal attached. */
export async function runStartForeground(opts: StartOptions): Promise<void> {
  console.log("note-connector — ChatGPT Connector セットアップ中…");
  const report = await setupDependencies();
  for (const w of report.warnings) {
    console.warn(`⚠ ${w}`);
  }
  loadOrCreateToken();
  const fqdn = discoverTailscaleFqdn();
  if (fqdn) {
    const config = loadConfig();
    if (!config.tunnel.domain) {
      saveConfig({ ...config, tunnel: { ...config.tunnel, domain: fqdn } });
      console.log(`Tailscale FQDN: ${fqdn}`);
    }
  }
  console.log("依存関係の準備が完了しました。");
  const config = loadConfig();
  const preferred = opts.port ?? config.gatewayPort;
  let port: number;
  try {
    port = await resolveGatewayPort(preferred, "127.0.0.1");
  } catch (e) {
    console.error((e as Error).message);
    process.exit(1);
  }
  if (port !== config.gatewayPort && opts.port === undefined) {
    saveConfig({ ...config, gatewayPort: port });
    console.log(`Using free port ${port} (saved to config; avoids LocalAnt 8787/8788).`);
  } else if (port !== preferred) {
    console.log(`Using free port ${port} (preferred ${preferred} was busy).`);
  }
  const tokenFile = path.join(configDir(), "token");
  loadOrCreateToken();

  const tunnel = new TunnelManager();
  let tunnelHost: string | undefined;

  const tunnelHostHint = config.tunnel.domain ?? (config.tunnel.publicUrl ? new URL(config.tunnel.publicUrl).host : undefined);
  const pidFile = path.join(configDir(), "note-connector.pid");
  fs.writeFileSync(pidFile, String(process.pid));

  const child = startPythonServer({
    host: "127.0.0.1",
    port,
    tokenFile,
    tunnelHost: tunnelHostHint,
  });

  for (let i = 0; i < 30; i++) {
    if (await verifyHealth(port)) break;
    await new Promise((r) => setTimeout(r, 500));
  }

  if (!opts.noTunnel) {
    const info = await tunnel.start(port, config.tunnel);
    if (info.url) {
      try {
        tunnelHost = new URL(info.url).host;
      } catch {
        tunnelHost = undefined;
      }
      if (tunnelHost) {
        process.env.NOTE_CONNECTOR_TUNNEL_HOST = tunnelHost;
      }
    }
  }

  const token = fs.readFileSync(tokenFile, "utf8").trim();
  const localUrl = buildMcpEndpoint(`http://127.0.0.1:${port}`, token);
  const t = tunnel.current();
  const publicUrl = t.url ? buildMcpEndpoint(t.url, token) : localUrl;

  console.log("");
  console.log("note-connector is running");
  console.log(`Local MCP: ${localUrl}`);

  if (t.url) {
    console.log(`Public MCP: ${publicUrl}`);
  } else if (t.error) {
    console.log(`Tunnel: ${t.error}`);
    console.log("Public URL なし → 下記はローカル用です。ChatGPT にはトンネル成功後の URL が必要です。");
    const fqdn = discoverTailscaleFqdn();
    if (fqdn) {
      console.log(`Fix: note-connector config set tunnel.domain ${fqdn}`);
      console.log(`     tailscale funnel ${port}`);
    }
  }

  const noteOk = isNoteAuthenticated();
  if (!noteOk && !opts.skipNoteLogin) {
    startNoteLoginInBackground();
  }

  await runOnboarding({
    publicMcpUrl: publicUrl,
    localMcpUrl: localUrl,
    noteAuthenticated: noteOk,
    tunnelOk: Boolean(t.url),
    noOpen: opts.noOpen,
    noClipboard: opts.noClipboard,
  });

  child.on("exit", (code, signal) => {
    if (code !== 0 && code !== null) {
      console.error(
        `Python MCP server exited (code=${code}${signal ? `, signal=${signal}` : ""}).\n` +
          `If you saw 'address already in use', another app owns the port — stop LocalAnt or change gatewayPort.`,
      );
      process.exit(code ?? 1);
    }
  });

  const shutdown = () => {
    tunnel.stop();
    child.kill("SIGTERM");
    try {
      fs.rmSync(pidFile, { force: true });
    } catch {
      /* ignore */
    }
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  await new Promise(() => {});
}
