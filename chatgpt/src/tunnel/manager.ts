import { spawn, type ChildProcess } from "node:child_process";
import type { TunnelConfig } from "../config.js";
import {
  discoverTailscaleFqdn,
  funnelReset,
  parseTailscaleFunnelUrl,
  resolveTailscaleBin,
  tailscaleEnv,
} from "./tailscale.js";

export interface TunnelInfo {
  provider: string;
  url?: string;
  status: "starting" | "running" | "stopped" | "error";
  error?: string;
}

export class TunnelManager {
  private child?: ChildProcess;
  private info: TunnelInfo = { provider: "none", status: "stopped" };
  private timeoutId?: NodeJS.Timeout;

  current(): TunnelInfo {
    return this.info;
  }

  stop(): void {
    if (this.timeoutId) clearTimeout(this.timeoutId);
    if (this.child) {
      this.child.kill();
      this.child = undefined;
    }
    this.info = { provider: "none", status: "stopped" };
  }

  async start(port: number, tunnel: TunnelConfig): Promise<TunnelInfo> {
    if (tunnel.publicUrl) {
      this.info = { provider: "custom", url: tunnel.publicUrl.replace(/\/$/, ""), status: "running" };
      return this.info;
    }

    if (tunnel.provider === "none") {
      this.info = { provider: "none", status: "stopped" };
      return this.info;
    }

    if (tunnel.provider === "tailscale") {
      return this.startTailscale(port, tunnel);
    }
    if (tunnel.provider === "ngrok") {
      return this.startNgrok(port, tunnel);
    }

    this.info = {
      provider: tunnel.provider,
      status: "error",
      error: `Unknown tunnel provider '${tunnel.provider}'.`,
    };
    return this.info;
  }

  private stableTailscaleUrl(tunnel: TunnelConfig): string | undefined {
    if (tunnel.domain) return `https://${tunnel.domain.replace(/^https?:\/\//, "").replace(/\/$/, "")}`;
    const discovered = discoverTailscaleFqdn();
    if (discovered) return `https://${discovered}`;
    return undefined;
  }

  private startTailscale(port: number, tunnel: TunnelConfig): Promise<TunnelInfo> {
    return new Promise((resolve) => {
      this.info = { provider: "tailscale", status: "starting" };
      const bin = resolveTailscaleBin();
      if (!bin) {
        this.info = {
          provider: "tailscale",
          status: "error",
          error: "Tailscale not found. Install from https://tailscale.com/download or set tunnel.publicUrl.",
        };
        resolve(this.info);
        return;
      }

      const stableUrl = this.stableTailscaleUrl(tunnel);
      funnelReset(bin);

      const env = tailscaleEnv();
      this.child = spawn(bin, ["funnel", String(port)], { env, shell: false });
      let acc = "";

      const finishRunning = (url: string) => {
        if (this.info.status === "running") return;
        this.info = { provider: "tailscale", url: url.replace(/\/$/, ""), status: "running" };
        if (this.timeoutId) clearTimeout(this.timeoutId);
        resolve(this.info);
      };

      const onData = (chunk: Buffer) => {
        acc += chunk.toString("utf8");
        const parsed = parseTailscaleFunnelUrl(acc);
        if (parsed) finishRunning(parsed);
      };

      this.child.stdout?.on("data", onData);
      this.child.stderr?.on("data", onData);
      this.child.on("error", (e) => {
        this.info = { provider: "tailscale", status: "error", error: e.message };
        resolve(this.info);
      });
      this.child.on("close", (code) => {
        if (this.info.status === "running") return;
        if (stableUrl) {
          finishRunning(stableUrl);
          return;
        }
        this.info = {
          provider: "tailscale",
          status: "error",
          error:
            `Tailscale Funnel exited (code ${code ?? "?"}). ` +
            "Enable Funnel in the admin console, or run: tailscale funnel " +
            port,
        };
        resolve(this.info);
      });

      this.timeoutId = setTimeout(() => {
        if (this.info.status === "running") return;
        if (stableUrl) {
          finishRunning(stableUrl);
          return;
        }
        this.info = {
          provider: "tailscale",
          status: "error",
          error:
            "Timed out waiting for Tailscale Funnel URL. Run once: tailscale funnel " +
            port +
            " (approve in admin), then: note-connector config set tunnel.domain <your-machine.ts.net>",
        };
        resolve(this.info);
      }, 45_000);
    });
  }

  private startNgrok(port: number, tunnel: TunnelConfig): Promise<TunnelInfo> {
    return new Promise((resolve) => {
      this.info = { provider: "ngrok", status: "starting" };
      const args = ["http", String(port), "--log", "stdout"];
      if (tunnel.domain) args.push("--domain", tunnel.domain);
      if (tunnel.token) args.push("--authtoken", tunnel.token);
      this.child = spawn("ngrok", args, { shell: false });
      let buf = "";
      const onData = (chunk: Buffer) => {
        buf += chunk.toString("utf8");
        const m = buf.match(/https:\/\/[a-z0-9-]+\.ngrok[a-z0-9.-]*\.(app|io)/i);
        if (m && this.info.status !== "running") {
          this.info = { provider: "ngrok", url: m[0], status: "running" };
          resolve(this.info);
        }
      };
      this.child.stdout?.on("data", onData);
      this.child.stderr?.on("data", onData);
      this.child.on("error", (e) => {
        this.info = { provider: "ngrok", status: "error", error: e.message };
        resolve(this.info);
      });
      setTimeout(() => {
        if (this.info.status === "running") return;
        if (tunnel.domain) {
          this.info = {
            provider: "ngrok",
            url: `https://${tunnel.domain}`,
            status: "running",
          };
          resolve(this.info);
        } else {
          this.info = { provider: "ngrok", status: "error", error: "Timed out waiting for ngrok URL" };
          resolve(this.info);
        }
      }, 20_000);
    });
  }
}
