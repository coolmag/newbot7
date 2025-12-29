const CACHE_NAME = 'aurora-player-v20';
const ASSETS = [
    './', './index.html', './style.css',
    './js/main.js', './js/api.js', './js/player.js',
    './js/store.js', './js/ui.js', './js/genres.js', 
    './js/visualizer.js', './js/haptics.js'
];

self.addEventListener('install', e => {
    self.skipWaiting(); 
    e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)));
});

self.addEventListener('activate', e => {
    e.waitUntil(caches.keys().then(cacheNames => {
        return Promise.all(
            cacheNames.map(cacheName => {
                if (cacheName !== CACHE_NAME) {
                    console.log('[SW] Deleting old cache:', cacheName);
                    return caches.delete(cacheName);
                }
            })
        );
    }).then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
    if (e.request.method !== 'GET') return;
    if (e.request.url.includes('/api/') || e.request.url.includes('/audio/')) {
        e.respondWith(fetch(e.request));
        return;
    }
    e.respondWith(caches.match(e.request).then(r => {
        // Fallback to network and cache the new resource.
        return r || fetch(e.request).then(response => {
            return caches.open(CACHE_NAME).then(cache => {
                cache.put(e.request, response.clone());
                return response;
            });
        });
    }));
});