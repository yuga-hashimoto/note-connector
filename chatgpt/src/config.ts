import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { configDir, ensureConfigDir } from "./paths.js";

export type TunnelProvider = "tailscale" | "ngrok" | "cloudflared" | "localtunnel" | "none";

export interface TunnelConfig {
  provider: TunnelProvider;
  domain?: string;
  subdomain?: string;
  token?: string;
  publicUrl?: string;
}

export interface NoteConnectorConfig {
  gatewayPort: number;
  tunnel: TunnelConfig;
  /** Path to git clone with src/note_mcp (required when CLI is npm global-only). */
  repoPath?: string;
}

/** Old default collided with LocalAnt — migrate on load. */
export const LEGACY_GATEWAY_PORT = 8787;

const DEFAULT_CONFIG: NoteConnectorConfig = {
  gatewayPort: 8797,
  tunnel: {
    provider: "tailscale",
  },
};

export function configPath(): string {
  return path.join(configDir(), "config.json");
}

export function tokenPath(): string {
  return path.join(configDir(), "token");
}

export function loadConfig(): NoteConnectorConfig {
  const file = configPath();
  if (!fs.existsSync(file)) {
    return { ...DEFAULT_CONFIG, tunnel: { ...DEFAULT_CONFIG.tunnel } };
  }
  const raw = JSON.parse(fs.readFileSync(file, "utf8")) as Partial<NoteConnectorConfig>;
  let gatewayPort = raw.gatewayPort ?? DEFAULT_CONFIG.gatewayPort;
  if (gatewayPort === LEGACY_GATEWAY_PORT) {
    gatewayPort = DEFAULT_CONFIG.gatewayPort;
    saveConfig({
      gatewayPort,
      tunnel: { ...DEFAULT_CONFIG.tunnel, ...raw.tunnel },
    });
  }
  return {
    gatewayPort,
    tunnel: { ...DEFAULT_CONFIG.tunnel, ...raw.tunnel },
  };
}

export function saveConfig(config: NoteConnectorConfig): void {
  ensureConfigDir();
  fs.writeFileSync(configPath(), JSON.stringify(config, null, 2));
}

export function loadOrCreateToken(): string {
  ensureConfigDir();
  const file = tokenPath();
  if (fs.existsSync(file)) {
    const t = fs.readFileSync(file, "utf8").trim();
    if (t) return t;
  }
  const token = crypto.randomBytes(32).toString("base64url");
  fs.writeFileSync(file, token, "utf8");
  return token;
}

export function buildMcpEndpoint(publicBase: string, token: string): string {
  return `${publicBase.replace(/\/$/, "")}/mcp?key=${token}`;
}
