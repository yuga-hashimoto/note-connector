#!/usr/bin/env node
/**
 * Sync version from chatgpt/package.json to server.json and pyproject.toml.
 * Usage: node scripts/sync-versions.mjs [version]
 * If version omitted, reads chatgpt/package.json.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const npmPkgPath = path.join(root, "chatgpt", "package.json");
const npmPkg = JSON.parse(fs.readFileSync(npmPkgPath, "utf8"));
const version = process.argv[2]?.replace(/^v/, "") ?? npmPkg.version;

npmPkg.version = version;
fs.writeFileSync(npmPkgPath, JSON.stringify(npmPkg, null, 2) + "\n");

const serverPath = path.join(root, "server.json");
const server = JSON.parse(fs.readFileSync(serverPath, "utf8"));
server.version = version;
if (Array.isArray(server.packages)) {
  for (const p of server.packages) {
    if (p.identifier === "note-connector") p.version = version;
  }
}
fs.writeFileSync(serverPath, JSON.stringify(server, null, 2) + "\n");

const pyprojectPath = path.join(root, "pyproject.toml");
let py = fs.readFileSync(pyprojectPath, "utf8");
py = py.replace(/^version = ".*"$/m, `version = "${version}"`);
fs.writeFileSync(pyprojectPath, py);

console.log(`Synced version ${version} → chatgpt/package.json, server.json, pyproject.toml`);
