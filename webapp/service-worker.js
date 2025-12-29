const CACHE_NAME = 'aurora-player-v2'; // ИЗМЕНЕНО: v2 для сброса кэша
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
    // visualizer.js не кешируем жестко, чтобы он не ломал загрузку
];

self.addEventListener('install', event => {
    self.skipWaiting(); // Форсируем обновление
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS_TO_CACHE))
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim()) // Немедленно берем контроль
    );
});

self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') return;

    // API и Audio всегда мимо кэша
    if (event.request.url.includes('/api/') || event.request.url.includes('/audio/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    event.respondWith(
        caches.match(event.request)
            .then(cachedResponse => {
                // Если есть в кэше - отдаем
                if (cachedResponse) return cachedResponse;
                // Если нет - качаем и кешируем
                return fetch(event.request).then(networkResponse => {
                    if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
                        return networkResponse;
                    }
                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseToCache);
                    });
                    return networkResponse;
                });
            })
    );
});