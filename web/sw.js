// web/sw.js
// Keeps the viewer working offline: the app's own files are fetched fresh
// when online (so a new release loads whole, never part old and part new)
// and kept in the cache for when there is no connection.  Dictionaries
// live in IndexedDB, not here.
const CACHE = "stenolab-viewer-v2";
const APP_FILES = [
  "./", "index.html", "style.css", "app.js", "rtf.js",
  "manifest.webmanifest", "icon-180.png", "icon-192.png", "icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(APP_FILES)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      try {
        const response = await fetch(event.request, { cache: "no-cache" });
        if (response.ok) cache.put(event.request, response.clone());
        return response;
      } catch (e) {
        const cached = await cache.match(event.request, { ignoreSearch: true });
        if (cached) return cached;
        throw e;
      }
    })
  );
});
