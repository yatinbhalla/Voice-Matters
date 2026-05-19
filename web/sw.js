// Placeholder service worker. Real caching strategy lands in Prompt 2.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => { /* no-op */ });
