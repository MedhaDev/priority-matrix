// Service worker: makes the app open offline and installable.
//   Pages        → network first, fall back to the cached copy when offline
//   /assets/*    → cache first (Vite gives every build new file names, so these never go stale)
//   Fonts (Fontshare) → cache, refresh in the background
// Bump VERSION if you change this file's caching rules.
const VERSION = "pm-v2";
const SHELL = ["/", "/manifest.webmanifest", "/favicon.svg", "/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function networkFirst(request) {
  const cache = await caches.open(VERSION);
  try {
    const fresh = await fetch(request);
    if (fresh.ok) cache.put("/", fresh.clone());
    return fresh;
  } catch {
    return (await cache.match("/")) || Response.error();
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok) cache.put(request, res.clone());
  return res;
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(request);
  const refresh = fetch(request)
    .then((res) => { if (res.ok || res.type === "opaque") cache.put(request, res.clone()); return res; })
    .catch(() => hit);
  return hit || refresh;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  if (request.mode === "navigate") event.respondWith(networkFirst(request));
  else if (url.origin === location.origin && (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/"))) event.respondWith(cacheFirst(request));
  else if (url.hostname === "api.fontshare.com" || url.hostname === "cdn.fontshare.com") event.respondWith(staleWhileRevalidate(request));
});
