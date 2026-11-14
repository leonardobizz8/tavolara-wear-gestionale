/**
 * Tavolara Wear — Service Worker (PWA Offline & Asset Cache)
 */

const CACHE_NAME = "tavolara-pwa-v1";
const STATIC_ASSETS = [
  "/",
  "/admin",
  "/css/admin.css",
  "/css/style.css",
  "/js/admin.js",
  "/js/app.js",
  "/js/chart.umd.min.js",
  "/manifest.json",
  "/assets/favicon-48.png",
  "/assets/favicon-192.png",
  "/assets/favicon-512.png",
  "/assets/apple-touch-icon.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Dynamic API calls: Network-First (always fresh data, do not cache stale financial figures)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(JSON.stringify({ error: true, message: "Offline: connessione non disponibile." }), {
          headers: { "Content-Type": "application/json" }
        });
      })
    );
    return;
  }

  // Static Assets: Stale-While-Revalidate (instant load + background refresh)
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && event.request.method === "GET") {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      }).catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});
