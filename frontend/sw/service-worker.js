/* Maine Material Handling DMS service worker (Phase 13).
 *
 * Keeps the app's own files on the device so it opens without a connection.
 * It never stores data from the server: /api/ requests always go to the
 * network. The saved copy of units lives in IndexedDB, managed by the app.
 *
 * The version and the file list are filled in at build time (vite.config.ts).
 */
const VERSION = "__VERSION__";
const ASSETS = __ASSETS__;
const CACHE = `mmh-app-${VERSION}`;
const SHELL = "/";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll([SHELL, ...ASSETS])),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("mmh-app-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

const PASS_THROUGH = ["/api/", "/django-admin", "/healthz", "/readyz", "/sw.js"];

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (PASS_THROUGH.some((p) => url.pathname.startsWith(p))) return;

  if (request.mode === "navigate") {
    // Pages: the live server first; its own copy of the app if that fails.
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.status >= 500) throw new Error(`server ${response.status}`);
          return response;
        })
        .catch(() => caches.open(CACHE).then((cache) => cache.match(SHELL)))
        .then((response) => response || Response.error()),
    );
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    // Built files have the version in their name: the saved copy is always right.
    event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
  }
});
