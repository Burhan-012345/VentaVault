"""
VantaVault - PWA Manager
Handles Progressive Web App functionality
"""
import os
import json

class PWA_Manager:
    def __init__(self, app):
        self.app = app
        self.manifest_path = 'static/manifest.json'
        self.service_worker_path = 'static/js/service-worker.js'
        
        # Ensure static directories exist
        os.makedirs('static/css', exist_ok=True)
        os.makedirs('static/js', exist_ok=True)
        os.makedirs('static/icons', exist_ok=True)
    
    def generate_manifest(self):
        """Generate web app manifest"""
        manifest = {
            "name": "VantaVault",
            "short_name": "VantaVault",
            "description": "High-security media vault",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#000000",
            "theme_color": "#000000",
            "orientation": "portrait",
            "scope": "/",
            "icons": [
                {
                    "src": "/static/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable"
                }
            ],
            "categories": ["security", "productivity", "utilities"],
            "shortcuts": [
                {
                    "name": "Open Vault",
                    "short_name": "Vault",
                    "description": "Open secure vault",
                    "url": "/dashboard"
                },
                {
                    "name": "Add Media",
                    "short_name": "Add",
                    "description": "Add new media to vault",
                    "url": "/gallery?action=upload"
                }
            ]
        }
        
        # Write manifest file
        with open(self.manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
    
    def generate_service_worker(self):
        """Generate service worker for offline support"""
        sw_code = '''
// VantaVault Service Worker
const CACHE_NAME = 'vantavault-v1.0';
const STATIC_CACHE = 'vantavault-static-v1.0';

// Assets to cache on install
const STATIC_ASSETS = [
    '/',
    '/static/css/main.css',
    '/static/css/animations.css',
    '/static/js/app.js',
    '/static/js/auth.js',
    '/static/js/gallery.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/manifest.json'
];

// Install event - cache static assets
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE) {
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - network first, cache fallback
self.addEventListener('fetch', event => {
    // Skip non-GET requests and Chrome extensions
    if (event.request.method !== 'GET' || 
        event.request.url.startsWith('chrome-extension://')) {
        return;
    }

    // API calls - network only
    if (event.request.url.includes('/api/')) {
        event.respondWith(
            fetch(event.request)
                .catch(() => {
                    return new Response(
                        JSON.stringify({ error: 'You are offline' }),
                        { 
                            status: 503,
                            headers: { 'Content-Type': 'application/json' }
                        }
                    );
                })
        );
        return;
    }

    // Static assets - cache first, network fallback
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response;
                }
                
                return fetch(event.request)
                    .then(response => {
                        // Don't cache if not successful
                        if (!response || response.status !== 200) {
                            return response;
                        }

                        // Clone the response
                        const responseToCache = response.clone();

                        caches.open(CACHE_NAME)
                            .then(cache => {
                                cache.put(event.request, responseToCache);
                            });

                        return response;
                    })
                    .catch(() => {
                        // If offline and not in cache, show offline page
                        if (event.request.mode === 'navigate') {
                            return caches.match('/');
                        }
                        return new Response('Offline', { status: 503 });
                    });
            })
    );
});

// Background sync for uploads
self.addEventListener('sync', event => {
    if (event.tag === 'upload-media') {
        event.waitUntil(syncUploads());
    }
});

async function syncUploads() {
    // Implement background sync for failed uploads
    const db = await openUploadQueue();
    const uploads = await db.getAll('pending_uploads');
    
    for (const upload of uploads) {
        try {
            await retryUpload(upload);
            await db.delete('pending_uploads', upload.id);
        } catch (error) {
            console.error('Background sync failed:', error);
        }
    }
}

// Push notifications
self.addEventListener('push', event => {
    const options = {
        body: event.data.text(),
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/icon-192.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            {
                action: 'open',
                title: 'Open Vault'
            },
            {
                action: 'close',
                title: 'Close'
            }
        ]
    };

    event.waitUntil(
        self.registration.showNotification('VantaVault', options)
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();

    if (event.action === 'open') {
        event.waitUntil(
            clients.openWindow('/dashboard')
        );
    }
});
'''
        
        # Write service worker file
        with open(self.service_worker_path, 'w') as f:
            f.write(sw_code)
    
    def register_pwa(self):
        """Register PWA with Flask app"""
        # Generate manifest and service worker
        self.generate_manifest()
        self.generate_service_worker()
        
        # Add route handlers for PWA
        @self.app.route('/offline')
        def offline():
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>VantaVault - Offline</title>
                <style>
                    body {
                        background: #000;
                        color: #fff;
                        font-family: sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                    }
                    .container {
                        text-align: center;
                        padding: 2rem;
                    }
                    h1 {
                        color: #f5f5f5;
                        margin-bottom: 1rem;
                    }
                    p {
                        color: #aaa;
                        margin-bottom: 2rem;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>⚠️ Offline</h1>
                    <p>You are currently offline. Please reconnect to access VantaVault.</p>
                </div>
            </body>
            </html>
            '''