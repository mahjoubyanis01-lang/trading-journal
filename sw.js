const CACHE = 'tj-v1';
const ASSETS = [
  '/trading-journal/',
  '/trading-journal/index.html',
  '/trading-journal/app.js',
  '/trading-journal/style.css',
  '/trading-journal/manifest.json',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).catch(() => caches.match('/trading-journal/')))
  );
});
