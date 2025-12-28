const CACHE_NAME = 'neovinyl-v2025.1';
const ASSETS_TO_CACHE = [
    '/',
    '/index.html',
    '/style.css',
    '/js/main.js',
    '/js/visualizer.js',
    '/js/audio-engine.js',
    '/js/ui-manager.js',
    '/js/track-manager.js',
    '/assets/icons/vinyl-neon.svg',
    '/manifest.json'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS_TO_CACHE))
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
    if (event.request.url.includes('/api/')) {
        // Для API запросов используем сеть с fallback
        event.respondWith(
            fetch(event.request)
                .catch(() => caches.match(event.request))
        );
    } else {
        // Для статики используем кэш с обновлением
        event.respondWith(
            caches.match(event.request)
                .then(response => {
                    if (response) {
                        // Обновление кэша в фоне
                        fetch(event.request).then(networkResponse => {
                            caches.open(CACHE_NAME).then(cache => {
                                cache.put(event.request, networkResponse);
                            });
                        }).catch(() => {});
                        return response;
                    }
                    return fetch(event.request)
                        .then(networkResponse => {
                            return caches.open(CACHE_NAME)
                                .then(cache => {
                                    cache.put(event.request, networkResponse.clone());
                                    return networkResponse;
                                });
                        })
                        .catch(() => {
                            // Fallback для страниц
                            if (event.request.destination === 'document') {
                                return caches.match('/');
                            }
                        });
                })
        );
    }
});

// Background sync для сохранения плейлиста
self.addEventListener('sync', event => {
    if (event.tag === 'sync-playlist') {
        event.waitUntil(syncPlaylist());
    }
});

async function syncPlaylist() {
    const db = await openPlaylistDB();
    const offlineChanges = await getAllOfflineChanges(db);
    
    for (const change of offlineChanges) {
        try {
            await fetch('/api/playlist/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(change)
            });
            await removeOfflineChange(db, change.id);
        } catch (error) {
            console.error('Sync failed:', error);
        }
    }
}