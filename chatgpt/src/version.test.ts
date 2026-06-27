import test from "node:test";
import assert from "node:assert/strict";
import { APP_VERSION, isNewerVersion, resolveAppVersion } from "./version.js";

test("APP_VERSION matches package.json", () => {
  assert.equal(APP_VERSION, resolveAppVersion());
  assert.match(APP_VERSION, /^\d+\.\d+\.\d+/);
});

test("isNewerVersion", () => {
  assert.equal(isNewerVersion("1.0.1", "1.0.0"), true);
  assert.equal(isNewerVersion("1.0.0", "1.0.1"), false);
  assert.equal(isNewerVersion("2.0.0", "1.9.9"), true);
});
