/**
 * Tavolara Wear — Service Worker (Always Fresh Network-First with Instant Update)
 * Ensures every GitHub/Vercel deploy updates immediately across all mobile devices.
 */

const CACHE_NAME = "tavolara-pwa-v13";

self.addEventListener("install", (event) => {
  // Take control immediately
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Instantly purge all older caches and take control of all active tabs
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log("[SW] Eliminazione vecchia cache:", key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.action === "skipWaiting") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Dynamic API calls: pure network (never serve stale financial calculations)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(
          JSON.stringify({ error: true, message: "Offline: connessione al server non disponibile." }),
          { headers: { "Content-Type": "application/json" } }
        );
      })
    );
    return;
  }

  // Navigation requests (HTML pages): ALWAYS network-first with cache fallback
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseClone);
            });
          }
          return networkResponse;
        })
        .catch(() => caches.match(event.request).then(cached => cached || caches.match("/index.html")))
    );
    return;
  }

  // Static Assets (CSS, JS, Fonts, Images): Network-First
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && event.request.method === "GET") {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        return caches.match(event.request);
      })
  );
});
