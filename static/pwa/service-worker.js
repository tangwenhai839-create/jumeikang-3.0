const CACHE_NAME = 'jmk-pwa-shell-v1';
const OFFLINE_URL = '/static/pwa/offline.html';
const PRECACHE_URLS = [
  OFFLINE_URL,
  '/static/pwa/apple-touch-icon.png',
  '/static/pwa/icon-192.png',
  '/static/pwa/icon-512.png'
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(PRECACHE_URLS);
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(keys.filter(function(key) {
        return key.startsWith('jmk-pwa-') && key !== CACHE_NAME;
      }).map(function(key) {
        return caches.delete(key);
      }));
    }).then(function() {
      return self.clients.claim();
    })
  );
});

self.addEventListener('fetch', function(event) {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(function() {
        return caches.match(OFFLINE_URL);
      })
    );
    return;
  }

  if (PRECACHE_URLS.includes(url.pathname)) {
    event.respondWith(
      caches.match(request).then(function(cached) {
        return cached || fetch(request);
      })
    );
  }
});
