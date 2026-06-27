import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";

export function resolveTailscaleBin(): string | null {
  if (fs.existsSync("/Applications/Tailscale.app/Contents/MacOS/Tailscale")) {
    return "/Applications/Tailscale.app/Contents/MacOS/Tailscale";
  }
  return "tailscale";
}

export function tailscaleEnv(): NodeJS.ProcessEnv {
  if (process.env.SHLVL && process.env.SHLVL.length > 0) return process.env;
  return { ...process.env, SHLVL: "1" };
}

/** Public Funnel FQDN from `tailscale status --json` (Self.DNSName). */
export function discoverTailscaleFqdn(): string | undefined {
  const bin = resolveTailscaleBin();
  if (!bin) return undefined;
  try {
    const out = execFileSync(bin, ["status", "--json"], {
      encoding: "utf8",
      timeout: 8000,
      env: tailscaleEnv(),
    });
    const dns = (JSON.parse(out) as { Self?: { DNSName?: string } }).Self?.DNSName;
    if (!dns) return undefined;
    return dns.replace(/\.$/, "");
  } catch {
    return undefined;
  }
}

export function funnelReset(bin: string): void {
  try {
    execFileSync(bin, ["funnel", "reset"], {
      timeout: 10_000,
      stdio: "ignore",
      env: tailscaleEnv(),
    });
  } catch {
    /* best-effort */
  }
}

const TS_NET_URL = /https:\/\/[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net/i;

export function parseTailscaleFunnelUrl(text: string): string | undefined {
  const m = text.match(TS_NET_URL);
  return m?.[0];
}
