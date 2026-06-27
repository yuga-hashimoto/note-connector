import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { loadConfig, saveConfig, type NoteConnectorConfig } from "./config.js";
import { configDir, resolveNoteConnectorRepo } from "./paths.js";

const DEFAULT_REPO = "https://github.com/yuga-hashimoto/note-connector.git";

const MIN_NODE_MAJOR = 20;

export interface SetupReport {
  uvInstalled: boolean;
  repoReady: boolean;
  pythonDepsReady: boolean;
  playwrightReady: boolean;
  warnings: string[];
}

function commandExists(cmd: string): boolean {
  try {
    execFileSync("command", ["-v", cmd], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function installUvUnix(): void {
  console.log("Installing uv (Python toolchain)…");
  execFileSync(
    "sh",
    ["-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
    { stdio: "inherit", env: { ...process.env, CARGO_HOME: process.env.CARGO_HOME } },
  );
  const home = process.env.HOME ?? "";
  const cargoBin = path.join(home, ".cargo", "bin");
  const localBin = path.join(home, ".local", "bin");
  const pathEnv = process.env.PATH ?? "";
  if (!pathEnv.includes(cargoBin)) {
    process.env.PATH = `${cargoBin}:${localBin}:${pathEnv}`;
  }
}

function ensureUv(): void {
  if (commandExists("uv")) return;
  if (process.platform === "win32") {
    throw new Error("uv が見つかりません。https://docs.astral.sh/uv/ からインストールしてください。");
  }
  installUvUnix();
  if (!commandExists("uv")) {
    throw new Error("uv のインストールに失敗しました。PATH に ~/.local/bin または ~/.cargo/bin を追加してください。");
  }
}

function repoHasPython(root: string): boolean {
  return fs.existsSync(path.join(root, "pyproject.toml")) && fs.existsSync(path.join(root, "src", "note_mcp"));
}

function cloneRepo(target: string): void {
  console.log(`Cloning note-connector → ${target}`);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  execFileSync("git", ["clone", "--depth", "1", DEFAULT_REPO, target], { stdio: "inherit" });
}

function updateRepo(repo: string): void {
  try {
    const result = spawnSync("git", ["pull", "--ff-only", "origin", "main"], {
      cwd: repo,
      encoding: "utf8",
      timeout: 15000,
    });
    if (result.status === 0 && !String(result.stdout).trim().includes("Already up to date")) {
      console.log("note-connector を最新に更新しました");
    }
  } catch {
    // Network issues or git not available — skip silently
  }
}

function ensureRepoPath(config: NoteConnectorConfig): string {
  if (config.repoPath && repoHasPython(config.repoPath)) {
    return path.resolve(config.repoPath);
  }
  try {
    return resolveNoteConnectorRepo();
  } catch {
    /* fall through */
  }
  const target = path.join(configDir(), "repo");
  if (!repoHasPython(target)) {
    if (fs.existsSync(target)) {
      throw new Error(`Incomplete repo at ${target}. Remove it or set repoPath.`);
    }
    cloneRepo(target);
  }
  const updated = { ...config, repoPath: target };
  saveConfig(updated);
  process.env.NOTE_CONNECTOR_REPO = target;
  return target;
}

function runUvSync(repo: string): void {
  console.log("Installing Python dependencies (uv sync)…");
  execFileSync("uv", ["sync"], { cwd: repo, stdio: "inherit", env: process.env });
}

function ensurePlaywright(repo: string): void {
  console.log("Installing Playwright Chromium (初回のみ時間がかかります)…");
  execFileSync("uv", ["run", "playwright", "install", "chromium"], {
    cwd: repo,
    stdio: "inherit",
    env: process.env,
  });
}

function ensureNodeVersion(): void {
  const major = parseInt(process.versions.node.split(".")[0] ?? "0", 10);
  if (major < MIN_NODE_MAJOR) {
    throw new Error(`Node.js ${MIN_NODE_MAJOR}+ が必要です（現在: ${process.versions.node}）`);
  }
}

export async function setupDependencies(): Promise<SetupReport> {
  const warnings: string[] = [];
  ensureNodeVersion();
  const config = loadConfig();

  ensureUv();

  const repo = ensureRepoPath(config);
  updateRepo(repo);
  runUvSync(repo);
  ensurePlaywright(repo);

  if (!commandExists("tailscale") && config.tunnel.provider === "tailscale" && !config.tunnel.publicUrl) {
    warnings.push("Tailscale CLI がありません。tunnel.publicUrl を設定するか Tailscale をインストールしてください。");
  }

  return {
    uvInstalled: true,
    repoReady: true,
    pythonDepsReady: true,
    playwrightReady: true,
    warnings,
  };
}
