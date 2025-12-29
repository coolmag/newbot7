const CACHE_NAME = 'aurora-player-v3'; // ВЕРСИЯ 3
const ASSETS_TO_CACHE = [
    './',
    './index.html',
    './style.css',
    './js/main.js',
    './js/api.js',
    './js/player.js',
    './js/store.js',
    './js/ui.js',
    './js/genres.js'
];

self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS_TO_CACHE)));
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => Promise.all(
            cacheNames.map(name => {
                if (name !== CACHE_NAME) return caches.delete(name);
            })
        )).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') return;
    if (event.request.url.includes('/api/') || event.request.url.includes('/audio/')) {
        event.respondWith(fetch(event.request));
        return;
    }
    event.respondWith(
        caches.match(event.request).then(res => res || fetch(event.request))
    );
});