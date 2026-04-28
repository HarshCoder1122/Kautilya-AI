const CACHE_NAME = 'kautilya-cloud-v1';
const urlsToCache = [
'/',
'/static/style.css',
'/static/script.js',
'/static/manifest.json',
'/static/kautilya_logo.png',
'/static/icon-192.png',
'/static/icon-512.png'
];
self.addEventListener('install', event => {
event.waitUntil(
caches.open(CACHE_NAME)
.then(cache => cache.addAll(urlsToCache))
.then(() => self.skipWaiting())
);
});
self.addEventListener('activate', event => {
event.waitUntil(
caches.keys().then(cacheNames => {
return Promise.all(
cacheNames.map(cacheName => {
if (cacheName !== CACHE_NAME) {
return caches.delete(cacheName);
}
})
);
}).then(() => self.clients.claim())
);
});
self.addEventListener('fetch', event => {
if (event.request.method !== 'GET' || event.request.url.includes('/api/')) {
return;
}
event.respondWith(
caches.match(event.request)
.then(response => {
if (response) {
return response;
}
return fetch(event.request).then(networkResponse => {
if (networkResponse && networkResponse.status === 200 &&
event.request.url.includes('/static/')) {
const responseToCache = networkResponse.clone();
caches.open(CACHE_NAME).then(cache => {
cache.put(event.request, responseToCache);
});
}
return networkResponse;
});
})
.catch(() => {
if (event.request.mode === 'navigate') {
return caches.match('/');
}
})
);
});