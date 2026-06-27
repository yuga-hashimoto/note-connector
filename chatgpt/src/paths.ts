import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export function configDir(): string {
  return process.env.NOTE_CONNECTOR_CONFIG_DIR ?? path.join(os.homedir(), ".note-connector");
}

/** Directory containing `src/note_mcp` (clone) or set via config / env. */
export function resolveNoteConnectorRepo(): string {
  const fromEnv = process.env.NOTE_CONNECTOR_REPO;
  if (fromEnv) {
    const root = path.resolve(fromEnv);
    if (fs.existsSync(path.join(root, "src", "note_mcp"))) return root;
  }
  const cfgFile = path.join(configDir(), "config.json");
  if (fs.existsSync(cfgFile)) {
    try {
      const cfg = JSON.parse(fs.readFileSync(cfgFile, "utf8")) as { repoPath?: string };
      if (cfg.repoPath) {
        const root = path.resolve(cfg.repoPath);
        if (fs.existsSync(path.join(root, "src", "note_mcp"))) return root;
      }
    } catch {
      /* ignore */
    }
  }
  const here = path.dirname(fileURLToPath(import.meta.url));
  const fromDevLayout = path.resolve(here, "..", "..");
  if (fs.existsSync(path.join(fromDevLayout, "src", "note_mcp"))) {
    return fromDevLayout;
  }
  const fromGlobal = path.resolve(here, "..");
  if (fs.existsSync(path.join(fromGlobal, "src", "note_mcp"))) {
    return fromGlobal;
  }
  throw new Error(
    "note-connector Python 本体が見つかりません。\n"
      + "  git clone https://github.com/drillan/note-mcp.git\n"
      + "  note-connector config set repoPath /path/to/note-connector\n"
      + "または NOTE_CONNECTOR_REPO=/path/to/note-connector を設定してください。",
  );
}

/** @deprecated use resolveNoteConnectorRepo */
export function repoRootFromPackage(): string {
  return resolveNoteConnectorRepo();
}

export function ensureConfigDir(): string {
  const dir = configDir();
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}
