#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { Command } from "commander";
import { loadConfig, saveConfig, type NoteConnectorConfig } from "./config.js";
import { runSetup, runStart, runStartForeground } from "./runtime.js";
import { isDaemonRunning, loadRuntime, loadLastMcpAccess, clearRuntime } from "./daemon-state.js";
import { configDir } from "./paths.js";
import { APP_VERSION, isNewerVersion } from "./version.js";

const program = new Command();
program.name("note-connector").description("ChatGPT connector for note.com").version(APP_VERSION);

program
  .command("start", { isDefault: true })
  .description("Start note-connector in background (MCP + tunnel); terminal can close after setup")
  .option("--no-tunnel", "Do not start a public tunnel")
  .option("-p, --port <number>", "Local port", (v) => parseInt(v, 10))
  .option("--no-open", "Do not open ChatGPT / note.com in the browser")
  .option("--no-clipboard", "Do not copy Public MCP URL to clipboard")
  .option("--skip-note-login", "Do not open Playwright note login")
  .option("--foreground", "Keep terminal open (debug)")
  .action(async (opts: { noTunnel?: boolean; port?: number; noOpen?: boolean; noClipboard?: boolean; skipNoteLogin?: boolean; foreground?: boolean }) => {
    const base = {
      noTunnel: Boolean(opts.noTunnel),
      port: opts.port,
      noOpen: Boolean(opts.noOpen),
      noClipboard: Boolean(opts.noClipboard),
      skipNoteLogin: Boolean(opts.skipNoteLogin),
    };
    if (opts.foreground) await runStartForeground(base);
    else await runStart(base);
  });

program
  .command("setup", { hidden: true })
  .description("Deprecated: use note-connector without arguments")
  .action(async () => {
    await runSetup();
  });

program
  .command("config")
  .description("Get or set configuration")
  .argument("[key]", "dotted key e.g. tunnel.domain")
  .argument("[value]", "value to set")
  .action((key?: string, value?: string) => {
    const config = loadConfig();
    if (!key) {
      console.log(JSON.stringify(config, null, 2));
      return;
    }
    if (value === undefined) {
      const parts = key.split(".");
      let cur: unknown = config;
      for (const p of parts) {
        cur = (cur as Record<string, unknown>)[p];
      }
      console.log(cur);
      return;
    }
    const updated = { ...config, tunnel: { ...config.tunnel } } as NoteConnectorConfig;
    if (key === "tunnel.provider") updated.tunnel.provider = value as NoteConnectorConfig["tunnel"]["provider"];
    else if (key === "tunnel.domain") updated.tunnel.domain = value;
    else if (key === "tunnel.subdomain") updated.tunnel.subdomain = value;
    else if (key === "tunnel.token") updated.tunnel.token = value;
    else if (key === "tunnel.publicUrl") updated.tunnel.publicUrl = value;
    else if (key === "gatewayPort") updated.gatewayPort = parseInt(value, 10);
    else if (key === "repoPath") updated.repoPath = value;
    else {
      console.error(`Unknown key: ${key}`);
      process.exit(1);
    }
    saveConfig(updated);
    console.log(`Set ${key}=${value}`);
  });


program
  .command("update")
  .description("Update note-connector to the latest npm release")
  .option("--check", "only check for a newer version")
  .option("--pm <manager>", "package manager (npm|pnpm|yarn|bun)", "npm")
  .action((o: { check?: boolean; pm?: string }) => {
    const current = APP_VERSION;
    let latest: string;
    try {
      latest = execFileSync("npm", ["view", "note-connector", "version"], { encoding: "utf8" }).trim();
    } catch {
      console.error(
        "Could not check npm for updates (package may not be published yet).\n"
        + "After first release: npm install -g note-connector@latest",
      );
      process.exit(1);
    }
    if (!isNewerVersion(latest, current)) {
      console.log(`Already up to date (v${current}).`);
      return;
    }
    console.log(`Update available: v${current} → v${latest}`);
    if (o.check) {
      console.log("Run `note-connector update` to install.");
      return;
    }
    const pm = String(o.pm ?? "npm");
    const installArgs: Record<string, string[]> = {
      npm: ["install", "-g", "note-connector@latest"],
      pnpm: ["add", "-g", "note-connector@latest"],
      yarn: ["global", "add", "note-connector@latest"],
      bun: ["add", "-g", "note-connector@latest"],
    };
    const args = installArgs[pm];
    if (!args) {
      console.error(`Unknown package manager: ${pm}`);
      process.exit(1);
    }
    console.log(`Installing note-connector@latest via ${pm}…`);
    execFileSync(pm, args, { stdio: "inherit" });
    console.log(`Updated to v${latest}.`);
  });



program
  .command("status")
  .description("Show background server status and last ChatGPT MCP access")
  .action(() => {
    if (!isDaemonRunning()) {
      console.log("note-connector は停止中です。起動: note-connector");
      return;
    }
    const rt = loadRuntime();
    const access = loadLastMcpAccess();
    console.log("note-connector: running (background)");
    if (rt) {
      console.log(`PID: ${rt.cliPid}`);
      console.log(`Public MCP: ${rt.publicMcpUrl}`);
      console.log(`ログ: ${rt.logFile}`);
      console.log(`起動: ${rt.startedAt}`);
    }
    if (access) {
      console.log(`最終 ChatGPT 接続: ${access.at}${access.remote ? ` (${access.remote})` : ""}`);
    }
  });

program
  .command("stop")
  .description("Stop background note-connector")
  .action(() => {
    const rt = loadRuntime();
    const pidFile = path.join(configDir(), "note-connector.pid");
    const pid = rt?.cliPid ?? (fs.existsSync(pidFile) ? parseInt(fs.readFileSync(pidFile, "utf8").trim(), 10) : NaN);
    if (!pid || Number.isNaN(pid)) {
      console.log("note-connector は動いていません。");
      clearRuntime();
      return;
    }
    try {
      process.kill(pid, "SIGTERM");
      console.log(`停止しました (PID ${pid})`);
    } catch {
      console.log(`PID ${pid} は既に終了しています。`);
    }
    clearRuntime();
  });


program.parseAsync(process.argv);