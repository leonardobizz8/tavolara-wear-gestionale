/**
 * Tavolara Wear — Service Worker (Always Fresh Network-First with Offline Fallback)
 * Ensures every GitHub/Vercel deploy updates instantly on all mobile devices.
 */

const CACHE_NAME = "tavolara-pwa-v3";

self.addEventListener("install", (event) => {
  // Activate immediately
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Instantly purge all older caches and take control of all clients
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

  // Network-First for HTML, CSS, JS and Assets:
  // Always fetches the latest live version from Vercel.
  // Falls back to cached version ONLY if completely offline.
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
