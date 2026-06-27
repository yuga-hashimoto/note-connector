import test from "node:test";
import assert from "node:assert/strict";
import { buildMcpEndpoint } from "./config.js";

test("buildMcpEndpoint", () => {
  assert.equal(
    buildMcpEndpoint("https://machine.tail.ts.net/", "abc"),
    "https://machine.tail.ts.net/mcp?key=abc",
  );
});
