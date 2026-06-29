import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import { finished } from "node:stream/promises";
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
    if (process.platform === "win32") {
      execFileSync("where.exe", [cmd], { stdio: "ignore" });
    } else {
      execFileSync("command", ["-v", cmd], { stdio: "ignore" });
    }
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

async function downloadUvZip(url: string, destPath: string): Promise<void> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to download uv: ${response.statusText}`);
  const fileStream = fs.createWriteStream(destPath);
  await finished(Readable.fromWeb(response.body as any).pipe(fileStream));
}

async function installUvWin32(): Promise<void> {
  console.log("Installing uv (Python toolchain) on Windows…");
  const userProfile = process.env.USERPROFILE ?? "";
  const localBin = path.join(userProfile, ".local", "bin");
  fs.mkdirSync(localBin, { recursive: true });

  const tempDir = path.join(process.env.TEMP ?? userProfile, `uv-install-${Date.now()}`);
  fs.mkdirSync(tempDir, { recursive: true });

  const zipUrl = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip";
  const zipPath = path.join(tempDir, "uv.zip");

  try {
    console.log("Downloading uv zip archive...");
    await downloadUvZip(zipUrl, zipPath);

    console.log("Extracting uv zip archive...");
    execFileSync("tar.exe", ["-xf", zipPath, "-C", tempDir], { stdio: "ignore" });

    const findUvExe = (dir: string): string | null => {
      const files = fs.readdirSync(dir);
      for (const file of files) {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);
        if (stat.isDirectory()) {
          const found = findUvExe(fullPath);
          if (found) return found;
        } else if (file.toLowerCase() === "uv.exe") {
          return fullPath;
        }
      }
      return null;
    };

    const uvExePath = findUvExe(tempDir);
    if (!uvExePath) {
      throw new Error("Could not find uv.exe in the extracted zip archive.");
    }

    const parentDir = path.dirname(uvExePath);
    for (const file of fs.readdirSync(parentDir)) {
      const src = path.join(parentDir, file);
      const dest = path.join(localBin, file);
      fs.copyFileSync(src, dest);
    }
    console.log(`uv successfully installed to ${localBin}`);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }

  const pathEnv = process.env.PATH ?? "";
  if (!pathEnv.toLowerCase().includes(localBin.toLowerCase())) {
    process.env.PATH = `${localBin};${pathEnv}`;
  }
}

async function ensureUv(): Promise<void> {
  if (commandExists("uv")) return;
  if (process.platform === "win32") {
    await installUvWin32();
  } else {
    installUvUnix();
  }
  if (!commandExists("uv")) {
    const pathHint = process.platform === "win32"
      ? "%USERPROFILE%\\.local\\bin"
      : "~/.local/bin または ~/.cargo/bin";
    throw new Error(`uv のインストールに失敗しました。PATH に ${pathHint} を追加してください。`);
  }
}

function repoHasPython(root: string): boolean {
  return fs.existsSync(path.join(root, "pyproject.toml")) && fs.existsSync(path.join(root, "src", "note_mcp"));
}

function npmPackagePythonRoot(): string | null {
  try {
    const root = resolveNoteConnectorRepo();
    return root;
  } catch {
    return null;
  }
}

function copyBundledPython(target: string): void {
  const source = npmPackagePythonRoot();
  if (!source) {
    throw new Error("npm パッケージにPythonソースが見つかりません。npm install -g を再実行してください。");
  }
  // Remove old repo and copy fresh from npm package
  if (fs.existsSync(target)) {
    fs.rmSync(target, { recursive: true, force: true });
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  console.log("Python ソースを npm からコピー中…");
  fs.cpSync(source, target, { recursive: true });
}

function updateRepo(target: string): void {
  // Prefer bundled npm copy over git pull
  const npmRoot = npmPackagePythonRoot();
  if (npmRoot && target !== npmRoot) {
    try {
      // Check which is newer: npm package vs local repo
      const npmSrcStat = fs.statSync(path.join(npmRoot, "src", "note_mcp", "server.py"));
      const localSrcStat = fs.statSync(path.join(target, "src", "note_mcp", "server.py"));
      if (npmSrcStat.mtimeMs > localSrcStat.mtimeMs) {
        copyBundledPython(target);
        console.log("note-connector を最新に更新しました（npm同梱版）");
        return;
      }
    } catch {
      // File stat failed, skip update
    }
  }
  // Fall back to git pull for manually cloned repos
  if (!commandExists("git")) return;
  try {
    const result = spawnSync("git", ["pull", "--ff-only", "origin", "main"], {
      cwd: target,
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
      // Incomplete, remove and retry
      fs.rmSync(target, { recursive: true, force: true });
    }
    // Try to copy from npm package first, fall back to git clone
    const npmRoot = npmPackagePythonRoot();
    if (npmRoot) {
      copyBundledPython(target);
    } else if (commandExists("git")) {
      console.log(`Cloning note-connector → ${target}`);
      execFileSync("git", ["clone", "--depth", "1", DEFAULT_REPO, target], { stdio: "inherit" });
    } else {
      throw new Error(
        "Python ソースが見つからず、git もありません。\n" +
          "npm install -g note-connector を再実行するか、\n" +
          "git clone でリポジトリを取得して repoPath を設定してください。",
      );
    }
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

  await ensureUv();

  const repo = ensureRepoPath(config);
  updateRepo(repo);
  runUvSync(repo);
  ensurePlaywright(repo);

  if (!commandExists("tailscale") && config.tunnel.provider === "tailscale" && !config.tunnel.publicUrl) {
    warnings.push("Tailscale CLI がありません。tunnel.publicUrl を設定するか Tailscale をインストールしてください。");
  }
  if (!commandExists("git")) {
    warnings.push(
      "git がありません。最新バージョンは npm install -g note-connector で更新されます。",
    );
  }

  return {
    uvInstalled: true,
    repoReady: true,
    pythonDepsReady: true,
    playwrightReady: true,
    warnings,
  };
}
