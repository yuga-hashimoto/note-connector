import test from "node:test";
import assert from "node:assert/strict";
import { RESERVED_PORTS, resolveGatewayPort } from "./net.js";

test("RESERVED_PORTS includes LocalAnt gateway", () => {
  assert.ok(RESERVED_PORTS.includes(8787));
});

test("resolveGatewayPort returns a free port", async () => {
  const port = await resolveGatewayPort(8797);
  assert.ok(port >= 8797);
  assert.ok(!RESERVED_PORTS.includes(port));
});
