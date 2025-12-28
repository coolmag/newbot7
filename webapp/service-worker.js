const CACHE_NAME = 'aurora-player-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/index.html',
    '/style.css',
    '/js/main.js',
    '/js/api.js',
    '/js/player.js',
    '/js/store.js',
    '/js/ui.js',
    '/js/visualizer.js'
];

// Install event: cache all static assets
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] Caching assets on install');
                return cache.addAll(ASSETS_TO_CACHE);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event: clean up old caches
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
        }).then(() => self.clients.claim())
    );
});

// Fetch event: serve from cache first, then network
self.addEventListener('fetch', event => {
    // We only want to cache GET requests.
    if (event.request.method !== 'GET') {
        return;
    }

    // For API and audio requests, always go to the network first.
    if (event.request.url.includes('/api/') || event.request.url.includes('/audio/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // For static assets, use a cache-first strategy.
    event.respondWith(
        caches.match(event.request)
            .then(cachedResponse => {
                // Return response from cache if available.
                if (cachedResponse) {
                    return cachedResponse;
                }

                // If not in cache, fetch from network.
                return fetch(event.request).then(networkResponse => {
                    // Don't cache opaque responses (e.g. from CDNs without CORS)
                    if(networkResponse.type === 'opaque') {
                        return networkResponse;
                    }

                    // Clone the response and cache it.
                    return caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, networkResponse.clone());
                        return networkResponse;
                    });
                });
            })
            .catch(error => {
                console.error('[SW] Fetch failed:', error);
                // You could return a fallback offline page here.
            })
    );
});
