import fs from "node:fs";
import path from "node:path";
import { configDir } from "./paths.js";

export interface DaemonRuntime {
  cliPid: number;
  port: number;
  publicMcpUrl: string;
  localMcpUrl: string;
  startedAt: string;
  logFile: string;
  tunnelProvider?: string;
}

export function runtimePath(): string {
  return path.join(configDir(), "runtime.json");
}

export function cliPidPath(): string {
  return path.join(configDir(), "note-connector.pid");
}

export function accessPath(): string {
  return path.join(configDir(), "last-mcp-access.json");
}

export function loadRuntime(): DaemonRuntime | null {
  const file = runtimePath();
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, "utf8")) as DaemonRuntime;
  } catch {
    return null;
  }
}

export function saveRuntime(runtime: DaemonRuntime): void {
  fs.mkdirSync(configDir(), { recursive: true });
  fs.writeFileSync(runtimePath(), JSON.stringify(runtime, null, 2));
}

export function clearRuntime(): void {
  for (const f of [runtimePath(), cliPidPath(), accessPath()]) {
    try {
      fs.rmSync(f, { force: true });
    } catch {
      /* ignore */
    }
  }
}

export function isProcessAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

export function isDaemonRunning(): boolean {
  const rt = loadRuntime();
  if (!rt) return false;
  return isProcessAlive(rt.cliPid);
}

export interface McpAccessRecord {
  at: string;
  remote?: string | null;
}

export function loadLastMcpAccess(): McpAccessRecord | null {
  const file = accessPath();
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, "utf8")) as McpAccessRecord;
  } catch {
    return null;
  }
}
