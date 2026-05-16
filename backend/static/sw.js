// Kautilya AI — service worker KILL-SWITCH.
// Older builds shipped a caching SW that now serves stale chunks (which
// have been renamed); this version unregisters itself and clears every
// cache, then forces every open tab to reload to pick up the fresh app.
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    try {
      const names = await caches.keys();
      await Promise.all(names.map((n) => caches.delete(n)));
    } catch (e) { /* ignore */ }
    try {
      await self.registration.unregister();
    } catch (e) { /* ignore */ }
    try {
      const clients = await self.clients.matchAll({ type: 'window' });
      clients.forEach((c) => { try { c.navigate(c.url); } catch (e) {} });
    } catch (e) { /* ignore */ }
  })());
});

// Never intercept network during the brief window this SW is active.
self.addEventListener('fetch', () => { /* no-op, pass through */ });
