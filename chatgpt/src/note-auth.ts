import { execFileSync, spawn } from "node:child_process";
import { repoRootFromPackage } from "./paths.js";

export function isNoteAuthenticated(): boolean {
  const root = repoRootFromPackage();
  try {
    execFileSync(
      "uv",
      [
        "run",
        "python",
        "-c",
        "from note_mcp.auth.session import SessionManager; import sys; sys.exit(0 if SessionManager().has_session() else 1)",
      ],
      { cwd: root, stdio: "ignore", timeout: 60_000 },
    );
    return true;
  } catch {
    return false;
  }
}

/** Start Playwright note login in background (does not block). */
export function startNoteLoginInBackground(): void {
  const root = repoRootFromPackage();
  const child = spawn("uv", ["run", "python", "-m", "note_mcp.chatgpt.login_once"], {
    cwd: root,
    stdio: "inherit",
    detached: true,
    shell: false,
  });
  child.unref();
}
