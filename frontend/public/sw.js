// Kautilya AI — Service Worker (PWA, install + offline shell).
// Strategy: network-first for navigation/API, cache-first for hashed
// static assets. We deliberately do NOT cache API responses so users
// always see live data when online.

const CACHE_VERSION = 'kautilya-v2';
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const STATIC_CACHE = `${CACHE_VERSION}-static`;

const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/logo.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) =>
      cache.addAll(SHELL_ASSETS).catch(() => {})
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(
      names
        .filter((n) => !n.startsWith(CACHE_VERSION))
        .map((n) => caches.delete(n))
    );
    await self.clients.claim();
  })());
});

function isStaticAsset(url) {
  return /\.(?:js|css|woff2?|ttf|png|jpg|jpeg|svg|gif|ico)$/.test(url.pathname);
}

function isApi(url) {
  return url.pathname.startsWith('/api/') ||
         url.hostname.includes('googleapis.com') ||
         url.hostname.includes('firebaseio.com') ||
         url.hostname.includes('firestore.googleapis.com');
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Never cache API / auth / streaming endpoints.
  if (isApi(url)) return;

  // SPA navigations — network-first, fall back to cached shell when offline.
  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(request);
        const cache = await caches.open(SHELL_CACHE);
        cache.put('/', fresh.clone()).catch(() => {});
        return fresh;
      } catch (e) {
        const cached = await caches.match('/') || await caches.match('/index.html');
        return cached || Response.error();
      }
    })());
    return;
  }

  // Static assets — cache-first with background refresh.
  if (isStaticAsset(url) && url.origin === self.location.origin) {
    event.respondWith((async () => {
      const cache = await caches.open(STATIC_CACHE);
      const cached = await cache.match(request);
      const networkPromise = fetch(request).then((resp) => {
        if (resp && resp.ok) cache.put(request, resp.clone()).catch(() => {});
        return resp;
      }).catch(() => null);
      return cached || (await networkPromise) || Response.error();
    })());
  }
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});
