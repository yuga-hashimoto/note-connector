import test from "node:test";
import assert from "node:assert/strict";
import { buildMcpEndpoint } from "./config.js";
import { buildRoutedMcpEndpoint } from "./shared-router.js";

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
