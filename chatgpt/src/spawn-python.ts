import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import { repoRootFromPackage } from "./paths.js";

export function startPythonServer(options: {
  host: string;
  port: number;
  tokenFile: string;
  tunnelHost?: string;
}): ChildProcess {
  const root = repoRootFromPackage();
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    HOME: process.env.HOME ?? process.env.USERPROFILE ?? "",
    NOTE_CONNECTOR_CONFIG_DIR: path.dirname(options.tokenFile),
  };
  if (options.tunnelHost) {
    env.NOTE_CONNECTOR_TUNNEL_HOST = options.tunnelHost;
  }
  return spawn(
    "uv",
    [
      "run",
      "python",
      "-m",
      "note_mcp.chatgpt",
      "--host",
      options.host,
      "--port",
      String(options.port),
      "--token-file",
      options.tokenFile,
    ],
    {
      cwd: root,
      env,
      stdio: "inherit",
      shell: false,
    },
  );
}
