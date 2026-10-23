const CACHE = 'tj-v2';
// Chemins relatifs au scope du service worker : fonctionne sur GitHub Pages
// (/trading-journal/) comme en local (http://127.0.0.1:876x/).
const ASSETS = [
  './',
  'index.html',
  'app.js',
  'style.css',
  'manifest.json',
  'options.html',
  'options.js',
  'icon-192.png',
  'icon-512.png',
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
  const url = new URL(e.request.url);
  // Les données d'options doivent toujours être fraîches : réseau d'abord.
  if (url.pathname.includes('/data/') || url.hostname === 'raw.githubusercontent.com') {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).catch(() => caches.match('./')))
  );
});
