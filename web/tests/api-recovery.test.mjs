import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { loadTs } from "./helpers/load-ts.mjs";

const api = loadTs("src/lib/api.ts");
const originalFetch = globalThis.fetch;
const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
beforeEach(() => Object.defineProperty(globalThis, "navigator", { configurable: true, value: { onLine: true } }));
afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalNavigator) Object.defineProperty(globalThis, "navigator", originalNavigator);
  else delete globalThis.navigator;
});

test("resuming an accepted receipt only reads that job and never uploads it again", async () => {
  const calls = [];
  const result = { transcript: "Fictional note", my_lang: "en-IN" };
  globalThis.fetch = async (url, init) => {
    calls.push([url, init?.method ?? "GET"]);
    return Response.json({ status: "done", result });
  };
  assert.deepEqual(await api.waitForJob("a".repeat(32), () => {}), result);
  assert.deepEqual(calls.map(([url, method]) => [new URL(url).pathname, method]), [["/v1/jobs/" + "a".repeat(32), "GET"]]);
});

test("expired receipts produce a specific failure without another upload", async () => {
  globalThis.fetch = async () => Response.json({ error: { code: "not_found", message: "Expired" } }, { status: 404 });
  await assert.rejects(api.waitForJob("b".repeat(32), () => {}), (error) => error.code === "not_found");
});

test("offline AI requests fail locally before any network or usage is incurred", async () => {
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { onLine: false } });
  let calls = 0;
  globalThis.fetch = async () => { calls++; throw new Error("Should not reach network"); };
  await assert.rejects(api.previewReply({ text: "Fictional", fromLang: "en-IN", toLang: "bn-IN", deviceId: "demo" }), (error) => error.code === "offline");
  assert.equal(calls, 0);
});
