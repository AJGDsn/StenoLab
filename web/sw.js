// web/sw.js
// Keeps the viewer working offline: the app's own files are cached on first
// visit and served from the cache, with a fresh copy fetched in the
// background for next time.  Dictionaries live in IndexedDB, not here.
const CACHE = "stenolab-viewer-v1";
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
      const cached = await cache.match(event.request, { ignoreSearch: true });
      const fresh = fetch(event.request)
        .then((response) => {
          if (response.ok) cache.put(event.request, response.clone());
          return response;
        })
        .catch(() => cached);
      return cached || fresh;
    })
  );
});
