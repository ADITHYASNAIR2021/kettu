import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { webcrypto } from "node:crypto";
import vm from "node:vm";

const source = (await readFile(new URL("../src/pwa/worker.js", import.meta.url), "utf8"))
  .replace('"__BUILD_ID__"', '"test-build"').replace('["__PRECACHE__"]', '["/", "/_next/static/app.js"]');
const origin = "https://kettu.example";

function worker({ offline = false, installFails = false } = {}) {
  const buckets = new Map();
  const listeners = new Map();
  const keyFor = (key) => new URL(typeof key === "string" ? key : key.url, origin).href;
  const caches = {
    async open(name) {
      if (!buckets.has(name)) buckets.set(name, new Map());
      const data = buckets.get(name);
      return {
        async addAll(keys) {
          if (installFails) throw new Error("Asset unavailable");
          for (const key of keys) data.set(keyFor(key), new Response(key));
        },
        async put(key, value) { data.set(keyFor(key), value); },
        async match(key) { return data.get(keyFor(key))?.clone(); },
        async delete(key) { return data.delete(keyFor(key)); },
        async keys() { return [...data.keys()].map((key) => new Request(key)); },
      };
    },
    async keys() { return [...buckets.keys()]; },
    async delete(name) { return buckets.delete(name); },
    async match(key) {
      for (const data of buckets.values()) if (data.has(keyFor(key))) return data.get(keyFor(key)).clone();
    },
  };
  vm.runInNewContext(source, {
    self: { location: { origin }, skipWaiting: async () => {}, clients: { claim: async () => {} }, addEventListener: (name, fn) => listeners.set(name, fn) },
    caches, Response, Request, URL, crypto: webcrypto, Date,
    fetch: async () => { if (offline) throw new Error("Offline"); return new Response("network"); },
  });
  return {
    caches, buckets,
    async install() {
      let pending; listeners.get("install")({ waitUntil(value) { pending = value; } }); await pending;
    },
    async fetch(path, mode) {
      let response;
      listeners.get("fetch")({ request: { url: new URL(path, origin).href, method: "GET", mode },
        respondWith(value) { response = value; }, waitUntil() {} });
      return await response;
    },
    async share(file) {
      const form = new FormData();
      form.append("audio", file, "note.ogg");
      let response;
      listeners.get("fetch")({ request: new Request(`${origin}/share-target`, { method: "POST", body: form }),
        respondWith(value) { response = value; } });
      return await response;
    },
    async activate() {
      let pending;
      listeners.get("activate")({ waitUntil(value) { pending = value; } });
      await pending;
    },
  };
}

test("a share redirects to an absolute URL and retains the correct audio", async () => {
  const app = worker();
  const response = await app.share(new Blob(["first note"], { type: "audio/ogg" }));
  assert.equal(response.status, 303);
  const location = new URL(response.headers.get("location"));
  assert.equal(location.origin, origin);
  const token = location.searchParams.get("shared");
  assert.match(token, /^[0-9a-f-]{36}$/);
  const cached = await (await app.caches.open("kettu-share-v1")).match(`/shared-audio/${token}`);
  assert.equal(await cached.text(), "first note");
});

test("two shares cannot overwrite each other's audio", async () => {
  const app = worker();
  const first = await app.share(new Blob(["one"]));
  const second = await app.share(new Blob(["two"]));
  assert.notEqual(first.headers.get("location"), second.headers.get("location"));
  assert.equal(app.buckets.get("kettu-share-v1").size, 2);
});

test("oversized shares are rejected before caching", async () => {
  const app = worker();
  const response = await app.share(new Blob([new Uint8Array(10 * 1024 * 1024 + 1)]));
  assert.equal(new URL(response.headers.get("location")).searchParams.get("shared"), "too_big");
  assert.equal(app.buckets.size, 0);
});

test("activation expires abandoned audio and keeps other applications' caches", async () => {
  const app = worker();
  const cache = await app.caches.open("kettu-share-v1");
  await cache.put("/old", new Response("old", { headers: { "X-Shared-At": String(Date.now() - 601000) } }));
  await cache.put("/recent", new Response("recent", { headers: { "X-Shared-At": String(Date.now()) } }));
  await app.caches.open("another-app");
  await app.caches.open("kettu-shell-v1");
  await app.caches.open("kettu-shell-v2");
  await app.activate();
  assert.equal(await cache.match("/old"), undefined);
  assert.ok(await cache.match("/recent"));
  assert.ok(app.buckets.has("another-app"));
  assert.equal(app.buckets.has("kettu-shell-v1"), false);
  assert.ok(app.buckets.has("kettu-shell-v2"));
});

test("offline navigation and lazy application chunks come from the public precache", async () => {
  const app = worker({ offline: true });
  await app.install();
  assert.equal(await (await app.fetch("/?shared=example", "navigate")).text(), "/");
  assert.equal(await (await app.fetch("/_next/static/app.js")).text(), "/_next/static/app.js");
});

test("API responses and private recordings are never handled by the shell cache", async () => {
  const app = worker(); await app.install();
  for (const path of ["https://api.example/jobs/123", "/api/jobs/123", "/shared-audio/secret", "/recording.ogg"])
    assert.equal(await app.fetch(path), undefined);
});

test("an incomplete precache fails installation rather than replacing the working worker", async () => {
  await assert.rejects(worker({ installFails: true }).install(), /Asset unavailable/);
});
