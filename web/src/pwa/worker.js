/* Kettu service worker.
 * 1. Share target: WhatsApp → Share → Kettu POSTs the voice note to /share-target.
 *    We park the file in Cache Storage and open /?shared=1, where the app picks it up.
 * 2. Keeps the app shell available so the share screen opens fast on slow networks.
 */
const SHARE_CACHE = "kettu-share-v1";
const SHELL_CACHE = "kettu-shell-" + "__BUILD_ID__";
const SHELL = ["__PRECACHE__"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => {
        const older = keys.filter((key) => key.startsWith("kettu-shell-") && key !== SHELL_CACHE);
        return Promise.all(older.slice(0, -1).map((key) => caches.delete(key)));
      })
      .then(clearExpiredShares)
      .then(() => self.clients.claim()),
  );
});

async function clearExpiredShares() {
  const cache = await caches.open(SHARE_CACHE);
  for (const key of await cache.keys()) {
    const response = await cache.match(key);
    const at = Number(response?.headers.get("X-Shared-At") || 0);
    if (!at || Date.now() - at > 600_000) await cache.delete(key);
  }
}

function redirect(value) {
  return Response.redirect(new URL(`/?shared=${value}`, self.location.origin).href, 303);
}

async function handleShare(request) {
  try {
    const form = await request.formData();
    const file = form.getAll("audio").find((f) => f && typeof f !== "string");
    if (!file) return redirect("empty");
    if (file.size > 10 * 1024 * 1024) return redirect("too_big");
    await clearExpiredShares();
    const token = crypto.randomUUID();
    const cache = await caches.open(SHARE_CACHE);
    await cache.put(
      `/shared-audio/${token}`,
      new Response(file, {
        headers: {
          "Content-Type": file.type || "audio/ogg",
          "X-Filename": encodeURIComponent(file.name || "voice-note.opus"),
          "X-Shared-At": String(Date.now()),
        },
      }),
    );
    return redirect(token);
  } catch {
    return redirect("error");
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
            event.waitUntil(caches.open(SHELL_CACHE).then((c) => c.put("/", copy)));
          }
          return resp;
        })
        .catch(() => caches.open(SHELL_CACHE).then(async (cache) =>
          await cache.match(url.pathname) || await cache.match("/") || Response.error())),
    );
    return;
  }
  if (request.method === "GET" && (
    /^\/_next\/static\/.*\.(?:js|css|woff2)$/.test(url.pathname)
    || url.pathname.startsWith("/icons/") || url.pathname === "/manifest.webmanifest"
  )) {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
  }
});
