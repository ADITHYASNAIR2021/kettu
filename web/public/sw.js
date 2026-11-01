/* Kettu service worker.
 * 1. Share target: WhatsApp → Share → Kettu POSTs the voice note to /share-target.
 *    We park the file in Cache Storage and open /?shared=1, where the app picks it up.
 * 2. Keeps the app shell available so the share screen opens fast on slow networks.
 */
const SHARE_CACHE = "kettu-share-v1";
const SHELL_CACHE = "kettu-shell-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((c) => c.addAll(SHELL)).catch(() => undefined).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => ![SHARE_CACHE, SHELL_CACHE].includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function handleShare(request) {
  try {
    const form = await request.formData();
    const file = form.getAll("audio").find((f) => f && typeof f !== "string");
    if (!file) return Response.redirect("/?shared=empty", 303);
    const cache = await caches.open(SHARE_CACHE);
    await cache.put(
      "/shared-audio",
      new Response(file, {
        headers: {
          "Content-Type": file.type || "audio/ogg",
          "X-Filename": encodeURIComponent(file.name || "voice-note.opus"),
          "X-Shared-At": String(Date.now()),
        },
      }),
    );
    return Response.redirect("/?shared=1", 303);
  } catch (e) {
    return Response.redirect("/?shared=error", 303);
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // never touch API calls

  if (request.method === "POST" && url.pathname === "/share-target") {
    event.respondWith(handleShare(request));
    return;
  }

  if (request.method === "GET" && request.mode === "navigate") {
    // Network first, cached shell when offline.
    event.respondWith(
      fetch(request)
        .then((resp) => {
          if (resp.ok && url.pathname === "/") {
            const copy = resp.clone();
            caches.open(SHELL_CACHE).then((c) => c.put("/", copy));
          }
          return resp;
        })
        .catch(() => caches.match("/").then((r) => r || Response.error())),
    );
  }
});
