const CACHE = 'whisperer-v5';

const SHELL = [
  '/',
  '/index.html',
  '/css/app.css',
  '/js/version.js',
  '/js/app.js',
  '/js/recorder.js',
  '/js/api.js',
  '/js/ui.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/genius_taic_logo.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = e.request.url;
  if (
    url.includes('/api/') ||
    url.includes('fonts.g') ||
    url.includes('/manifest/c/') ||
    /\/c\/[a-zA-Z0-9]+/.test(url)
  ) return;

  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
