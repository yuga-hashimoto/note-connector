import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { buildMcpEndpoint } from "./config.js";
import { buildRoutedMcpEndpoint, selectAvailableRouterPort } from "./shared-router.js";

test("buildMcpEndpoint", () => {
  assert.equal(
    buildMcpEndpoint("https://machine.tail.ts.net/", "abc"),
    "https://machine.tail.ts.net/mcp?key=abc",
  );
});

test("buildRoutedMcpEndpoint", () => {
  assert.equal(
    buildRoutedMcpEndpoint("https://machine.tail.ts.net/", "/note-connector", "abc"),
    "https://machine.tail.ts.net/note-connector/mcp?key=abc",
  );
});

test("selectAvailableRouterPort skips ports owned by another service", async () => {
  const otherService = http.createServer((_req, res) => {
    res.writeHead(404);
    res.end("not the shared router");
  });
  const occupiedPort = await new Promise<number>((resolve) => {
    otherService.listen(0, "127.0.0.1", () => {
      const address = otherService.address();
      resolve(typeof address === "object" && address ? address.port : 0);
    });
  });
  try {
    assert.notEqual(await selectAvailableRouterPort(occupiedPort), occupiedPort);
  } finally {
    await new Promise<void>((resolve) => otherService.close(() => resolve()));
  }
});
