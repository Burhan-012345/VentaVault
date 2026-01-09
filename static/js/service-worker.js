// VantaVault Service Worker
const CACHE_NAME = 'vantavault-v2.0';
const STATIC_CACHE = 'vantavault-static-v2.0';
const DYNAMIC_CACHE = 'vantavault-dynamic-v2.0';
const MEDIA_CACHE = 'vantavault-media-v2.0';

// Static assets to cache on install
const STATIC_ASSETS = [
    '/',
    '/static/css/main.css',
    '/static/css/animations.css',
    '/static/css/gallery.css',
    '/static/js/app.js',
    '/static/js/auth.js',
    '/static/js/gallery.js',
    '/manifest.json',
    '/offline',
    '/static/icons/icon-192.svg',
    '/static/icons/icon-512.svg'
];

// Install event - cache static assets
self.addEventListener('install', event => {
    console.log('[Service Worker] Installing VantaVault v2.0...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('[Service Worker] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('[Service Worker] All static assets cached');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('[Service Worker] Cache installation failed:', error);
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    console.log('[Service Worker] Activating...');
    
    const currentCaches = [CACHE_NAME, STATIC_CACHE, DYNAMIC_CACHE, MEDIA_CACHE];
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return cacheNames.filter(cacheName => {
                    // Delete old caches that aren't in currentCaches
                    return !currentCaches.includes(cacheName);
                });
            })
            .then(cachesToDelete => {
                return Promise.all(
                    cachesToDelete.map(cacheName => {
                        console.log('[Service Worker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    })
                );
            })
            .then(() => {
                console.log('[Service Worker] Claiming clients');
                return self.clients.claim();
            })
    );
});

// Fetch event handler
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    
    // Skip non-GET requests and Chrome extensions
    if (event.request.method !== 'GET' || 
        event.request.url.startsWith('chrome-extension://')) {
        return;
    }
    
    // Handle API requests differently
    if (url.pathname.startsWith('/api/')) {
        handleApiRequest(event);
        return;
    }
    
    // Handle media requests
    if (url.pathname.startsWith('/api/media/')) {
        handleMediaRequest(event);
        return;
    }
    
    // Handle HTML pages
    if (event.request.mode === 'navigate') {
        handlePageRequest(event);
        return;
    }
    
    // Handle static assets
    handleStaticRequest(event);
});

// API request handler
function handleApiRequest(event) {
    event.respondWith(
        fetch(event.request)
            .then(response => {
                // Don't cache API responses
                return response;
            })
            .catch(error => {
                console.error('[Service Worker] API request failed:', error);
                
                // Return offline response for API calls
                return new Response(
                    JSON.stringify({ 
                        error: 'You are offline',
                        offline: true,
                        timestamp: new Date().toISOString()
                    }),
                    { 
                        status: 503,
                        headers: { 
                            'Content-Type': 'application/json',
                            'Cache-Control': 'no-store'
                        }
                    }
                );
            })
    );
}

// Media request handler
function handleMediaRequest(event) {
    event.respondWith(
        caches.match(event.request)
            .then(cachedResponse => {
                // Return cached media if available
                if (cachedResponse) {
                    return cachedResponse;
                }
                
                // Otherwise fetch from network
                return fetch(event.request)
                    .then(response => {
                        // Cache successful responses
                        if (response.status === 200) {
                            const responseToCache = response.clone();
                            caches.open(MEDIA_CACHE)
                                .then(cache => {
                                    cache.put(event.request, responseToCache);
                                });
                        }
                        return response;
                    })
                    .catch(error => {
                        console.error('[Service Worker] Media fetch failed:', error);
                        
                        // Return placeholder for failed image requests
                        if (event.request.destination === 'image') {
                            return caches.match('/static/icons/icon-192.svg');
                        }
                        
                        return new Response('Media unavailable offline', { 
                            status: 503,
                            headers: { 'Content-Type': 'text/plain' }
                        });
                    });
            })
    );
}

// Page request handler
function handlePageRequest(event) {
    event.respondWith(
        fetch(event.request)
            .then(response => {
                // Cache the page
                const responseToCache = response.clone();
                caches.open(DYNAMIC_CACHE)
                    .then(cache => {
                        cache.put(event.request, responseToCache);
                    });
                return response;
            })
            .catch(error => {
                console.error('[Service Worker] Page fetch failed:', error);
                
                // Return cached page or offline page
                return caches.match(event.request)
                    .then(cachedResponse => {
                        if (cachedResponse) {
                            return cachedResponse;
                        }
                        return caches.match('/offline');
                    });
            })
    );
}

// Static asset request handler
function handleStaticRequest(event) {
    event.respondWith(
        caches.match(event.request)
            .then(cachedResponse => {
                if (cachedResponse) {
                    // Update cache in background
                    fetchAndCache(event.request);
                    return cachedResponse;
                }
                
                return fetchAndCache(event.request)
                    .catch(() => {
                        // If offline and not in cache
                        return new Response('Offline', { 
                            status: 503,
                            headers: { 'Content-Type': 'text/plain' }
                        });
                    });
            })
    );
}

// Helper function to fetch and cache
function fetchAndCache(request) {
    return fetch(request)
        .then(response => {
            // Don't cache if not successful
            if (!response || response.status !== 200) {
                return response;
            }
            
            // Clone the response
            const responseToCache = response.clone();
            
            caches.open(DYNAMIC_CACHE)
                .then(cache => {
                    cache.put(request, responseToCache);
                });
            
            return response;
        });
}

// Background sync for uploads
self.addEventListener('sync', event => {
    console.log('[Service Worker] Background sync:', event.tag);
    
    if (event.tag === 'sync-uploads') {
        event.waitUntil(syncPendingUploads());
    } else if (event.tag === 'sync-settings') {
        event.waitUntil(syncSettings());
    }
});

// Sync pending uploads
async function syncPendingUploads() {
    try {
        console.log('[Service Worker] Syncing pending uploads...');
        
        // Get pending uploads from IndexedDB
        const pendingUploads = await getPendingUploads();
        
        for (const upload of pendingUploads) {
            try {
                await retryUpload(upload);
                await removePendingUpload(upload.id);
                console.log('[Service Worker] Upload synced:', upload.id);
                
                // Send notification to client
                sendMessageToClient({
                    type: 'UPLOAD_SYNC_SUCCESS',
                    data: { id: upload.id }
                });
            } catch (error) {
                console.error('[Service Worker] Upload sync failed:', upload.id, error);
                
                sendMessageToClient({
                    type: 'UPLOAD_SYNC_FAILED',
                    data: { id: upload.id, error: error.message }
                });
            }
        }
    } catch (error) {
        console.error('[Service Worker] Background sync error:', error);
    }
}

// Sync settings
async function syncSettings() {
    try {
        console.log('[Service Worker] Syncing settings...');
        
        // Get offline settings changes
        const settingsChanges = await getOfflineSettings();
        
        for (const change of settingsChanges) {
            try {
                await syncSettingChange(change);
                await removeOfflineSetting(change.id);
                console.log('[Service Worker] Setting synced:', change.key);
            } catch (error) {
                console.error('[Service Worker] Setting sync failed:', change.key, error);
            }
        }
    } catch (error) {
        console.error('[Service Worker] Settings sync error:', error);
    }
}

// IndexedDB helper functions
async function getPendingUploads() {
    // This would connect to your IndexedDB database
    // For now, return empty array as placeholder
    return [];
}

async function retryUpload(upload) {
    // Implement retry logic
    return Promise.resolve();
}

async function removePendingUpload(id) {
    // Remove from IndexedDB
    return Promise.resolve();
}

async function getOfflineSettings() {
    // Get settings changed while offline
    return [];
}

async function syncSettingChange(change) {
    // Sync setting change to server
    return Promise.resolve();
}

async function removeOfflineSetting(id) {
    // Remove from IndexedDB
    return Promise.resolve();
}

// Push notifications
self.addEventListener('push', event => {
    console.log('[Service Worker] Push received');
    
    let data = {
        title: 'VantaVault',
        body: 'Security notification',
        icon: '/static/icons/icon-192.svg',
        badge: '/static/icons/icon-192.svg',
        tag: 'vantavault-notification'
    };
    
    if (event.data) {
        try {
            data = { ...data, ...event.data.json() };
        } catch (e) {
            data.body = event.data.text();
        }
    }
    
    const options = {
        body: data.body,
        icon: data.icon,
        badge: data.badge,
        vibrate: [100, 50, 100],
        data: data.data || {},
        tag: data.tag,
        requireInteraction: data.requireInteraction || false,
        actions: data.actions || [
            {
                action: 'open',
                title: 'Open Vault'
            },
            {
                action: 'dismiss',
                title: 'Dismiss'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Notification click handler
self.addEventListener('notificationclick', event => {
    console.log('[Service Worker] Notification clicked:', event.action);
    
    event.notification.close();
    
    if (event.action === 'open' || event.action === '') {
        event.waitUntil(
            clients.matchAll({
                type: 'window',
                includeUncontrolled: true
            }).then(clientList => {
                // Focus existing window
                for (const client of clientList) {
                    if (client.url.includes('/') && 'focus' in client) {
                        return client.focus();
                    }
                }
                
                // Open new window
                if (clients.openWindow) {
                    return clients.openWindow('/');
                }
            })
        );
    }
});

// Periodic background sync (for cleanup)
self.addEventListener('periodicsync', event => {
    if (event.tag === 'cleanup-cache') {
        event.waitUntil(cleanupCache());
    }
});

// Cache cleanup
async function cleanupCache() {
    console.log('[Service Worker] Running periodic cache cleanup');
    
    try {
        // Clean up old dynamic cache entries
        const cache = await caches.open(DYNAMIC_CACHE);
        const requests = await cache.keys();
        const oneWeekAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
        
        for (const request of requests) {
            const response = await cache.match(request);
            if (response) {
                const dateHeader = response.headers.get('date');
                if (dateHeader) {
                    const responseDate = new Date(dateHeader).getTime();
                    if (responseDate < oneWeekAgo) {
                        await cache.delete(request);
                    }
                }
            }
        }
        
        // Clean up old media cache
        const mediaCache = await caches.open(MEDIA_CACHE);
        const mediaRequests = await mediaCache.keys();
        const oneMonthAgo = Date.now() - (30 * 24 * 60 * 60 * 1000);
        
        for (const request of mediaRequests) {
            const response = await mediaCache.match(request);
            if (response) {
                const dateHeader = response.headers.get('date');
                if (dateHeader) {
                    const responseDate = new Date(dateHeader).getTime();
                    if (responseDate < oneMonthAgo) {
                        await mediaCache.delete(request);
                    }
                }
            }
        }
        
        console.log('[Service Worker] Cache cleanup completed');
    } catch (error) {
        console.error('[Service Worker] Cache cleanup failed:', error);
    }
}

// Message handler from clients
self.addEventListener('message', event => {
    console.log('[Service Worker] Message received:', event.data);
    
    if (event.data && event.data.type) {
        switch (event.data.type) {
            case 'SKIP_WAITING':
                self.skipWaiting();
                break;
                
            case 'CLEAR_CACHE':
                clearCache();
                break;
                
            case 'GET_CACHE_INFO':
                getCacheInfo().then(info => {
                    sendMessageToClient({
                        type: 'CACHE_INFO',
                        data: info
                    });
                });
                break;
                
            case 'CHECK_FOR_UPDATES':
                checkForUpdates();
                break;
        }
    }
});

// Clear all caches
async function clearCache() {
    const cacheNames = await caches.keys();
    await Promise.all(
        cacheNames.map(cacheName => caches.delete(cacheName))
    );
    console.log('[Service Worker] All caches cleared');
}

// Get cache information
async function getCacheInfo() {
    const cacheNames = await caches.keys();
    const info = {};
    
    for (const cacheName of cacheNames) {
        const cache = await caches.open(cacheName);
        const requests = await cache.keys();
        info[cacheName] = {
            count: requests.length,
            size: await calculateCacheSize(cache)
        };
    }
    
    return info;
}

// Calculate cache size
async function calculateCacheSize(cache) {
    const requests = await cache.keys();
    let totalSize = 0;
    
    for (const request of requests) {
        const response = await cache.match(request);
        if (response) {
            const blob = await response.blob();
            totalSize += blob.size;
        }
    }
    
    return totalSize;
}

// Check for updates
function checkForUpdates() {
    // This would check if a new service worker is available
    self.registration.update();
}

// Send message to client
function sendMessageToClient(message) {
    clients.matchAll().then(clients => {
        clients.forEach(client => {
            client.postMessage(message);
        });
    });
}

// Offline page (served when offline)
const OFFLINE_HTML = `
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VantaVault - Offline</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #000;
            color: #fff;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 20px;
        }
        
        .container {
            max-width: 400px;
        }
        
        .icon {
            font-size: 4rem;
            margin-bottom: 1.5rem;
            animation: pulse 2s infinite;
        }
        
        h1 {
            font-size: 2.5rem;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #fff, #aaa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        p {
            color: #aaa;
            margin-bottom: 2rem;
            line-height: 1.6;
        }
        
        .actions {
            display: flex;
            gap: 1rem;
            justify-content: center;
        }
        
        button {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 1rem;
        }
        
        button:hover {
            background: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        @media (max-width: 480px) {
            h1 { font-size: 2rem; }
            .icon { font-size: 3rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">⚠️</div>
        <h1>Offline</h1>
        <p>You are currently offline. Please reconnect to access your secure vault.</p>
        <div class="actions">
            <button onclick="window.location.reload()">Retry</button>
            <button onclick="window.location.href='/'">Go Home</button>
        </div>
    </div>
</body>
</html>
`;

// Cache the offline page on install
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                return cache.put('/offline', new Response(OFFLINE_HTML, {
                    headers: {
                        'Content-Type': 'text/html',
                        'Cache-Control': 'no-cache'
                    }
                }));
            })
    );
});

console.log('[Service Worker] VantaVault Service Worker loaded');