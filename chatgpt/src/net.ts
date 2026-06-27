import net from "node:net";

/** Ports commonly used by LocalAnt — note-connector never binds these. */
export const RESERVED_PORTS = [8787, 8788];

function isPortFree(port: number, host: string): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, host);
  });
}

/**
 * Pick a free port for note-connector, never using RESERVED_PORTS.
 * Scans upward from `preferred` (default 8797).
 */
export async function resolveGatewayPort(
  preferred: number,
  host = "127.0.0.1",
  attempts = 50,
): Promise<number> {
  const skip = new Set(RESERVED_PORTS);
  let start = preferred;
  if (skip.has(start)) {
    start = Math.max(...RESERVED_PORTS) + 1;
  }
  for (let i = 0; i < attempts; i++) {
    const port = start + i;
    if (port > 65535) break;
    if (skip.has(port)) continue;
    if (await isPortFree(port, host)) return port;
  }
  throw new Error(
    `No free port found from ${start} on ${host} (avoiding ${[...skip].join(", ")}).`,
  );
}
