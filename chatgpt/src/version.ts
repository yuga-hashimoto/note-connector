import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** Resolve version from the published `note-connector` package.json. */
export function resolveAppVersion(): string {
  try {
    let dir = dirname(fileURLToPath(import.meta.url));
    for (let i = 0; i < 10; i++) {
      try {
        const pkg = JSON.parse(readFileSync(join(dir, "package.json"), "utf8")) as {
          name?: string;
          version?: string;
        };
        if (pkg.name === "note-connector" && typeof pkg.version === "string") {
          return pkg.version;
        }
      } catch {
        /* keep walking */
      }
      const parent = dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  } catch {
    /* fall through */
  }
  return "0.0.0";
}

export const APP_VERSION = resolveAppVersion();

export function isNewerVersion(candidate: string, current: string): boolean {
  const parse = (v: string): number[] =>
    v.replace(/^v/, "").split(".").map((n) => parseInt(n, 10) || 0);
  const a = parse(candidate);
  const b = parse(current);
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const diff = (a[i] ?? 0) - (b[i] ?? 0);
    if (diff !== 0) return diff > 0;
  }
  return false;
}
