// Voice Matters - Sarkari Saathi service worker
//
// Route strategies (Sprint B Day 8):
//   - /api/v1/conversation/{id}/messages        -> stale-while-revalidate
//   - /api/v1/conversations                     -> stale-while-revalidate
//   - /api/v1/schemes/{id}                      -> cache-first (24h TTL)
//   - /api/v1/schemes/{id}/apply-steps          -> cache-first (24h TTL)
//   - /api/v1/schemes/{id}/explain              -> cache-first (7d TTL)
//   - /api/v1/messages/{id}/explanation         -> stale-while-revalidate
//   - /api/v1/conversation/{id}/voice|chat      -> network-only (write paths)
//   - /api/v1/feedback, /action                 -> network-only
//   - /static/audio/*                           -> cache-first (immutable)
//   - / and /index.html, fonts, icons           -> cache-first (precached)
//
// On offline (navigator.onLine false) we post a message to clients so the
// page can pop the No-network overlay. We also serve a JSON 503 fallback
// for write paths that miss network so JS catch() can branch correctly.

const VERSION = 'v9-apifetch-retry';
const STATIC_CACHE = 'vm-static-' + VERSION;
const SCHEMES_CACHE = 'vm-schemes-' + VERSION;
const MESSAGES_CACHE = 'vm-messages-' + VERSION;
const AUDIO_CACHE = 'vm-audio-' + VERSION;

const SCHEMES_TTL_MS = 24 * 60 * 60 * 1000;          // 24h
const EXPLAIN_TTL_MS = 7 * 24 * 60 * 60 * 1000;       // 7d

const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) =>
      Promise.all(
        PRECACHE_URLS.map((url) =>
          cache.add(new Request(url, { cache: 'reload' })).catch(() => {})
        )
      )
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  const keep = new Set([STATIC_CACHE, SCHEMES_CACHE, MESSAGES_CACHE, AUDIO_CACHE]);
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((n) => !keep.has(n)).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

// --- helpers ---------------------------------------------------------------

function jsonResponse(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

function offlineApiFallback() {
  return jsonResponse({ error: 'offline', message: 'You appear to be offline.' }, 503);
}

async function notifyOffline(clientId) {
  try {
    const clients = await self.clients.matchAll();
    clients.forEach(c => c.postMessage({ type: 'vm-offline' }));
  } catch (_e) { /* ignore */ }
}

function isExpired(cachedResponse, ttlMs) {
  if (!cachedResponse || !ttlMs) return false;
  const dateHdr = cachedResponse.headers.get('sw-cached-at')
    || cachedResponse.headers.get('date');
  if (!dateHdr) return false;
  const t = Date.parse(dateHdr);
  if (Number.isNaN(t)) return false;
  return (Date.now() - t) > ttlMs;
}

function stampedResponse(res) {
  // Tag the response with the cache time so isExpired() can reason about
  // TTL even after a process restart. Body stream is consumed once -> clone.
  const headers = new Headers(res.headers);
  headers.set('sw-cached-at', new Date().toUTCString());
  return res.clone().blob().then(blob => new Response(blob, {
    status: res.status,
    statusText: res.statusText,
    headers,
  }));
}

async function cacheFirst(req, cacheName, ttlMs) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if (cached && !isExpired(cached, ttlMs)) return cached;
  try {
    const fresh = await fetch(req);
    if (fresh && fresh.ok) {
      const stamped = await stampedResponse(fresh);
      cache.put(req, stamped.clone());
      return stamped;
    }
    return cached || fresh;
  } catch (err) {
    if (cached) return cached;
    notifyOffline();
    return offlineApiFallback();
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  const fetchPromise = fetch(req)
    .then(async (fresh) => {
      if (fresh && fresh.ok) {
        const stamped = await stampedResponse(fresh);
        cache.put(req, stamped.clone());
        return stamped;
      }
      return fresh;
    })
    .catch(() => null);
  if (cached) {
    // Kick revalidation in background; return cached immediately.
    event => event && event.waitUntil && event.waitUntil(fetchPromise);
    return cached;
  }
  const fresh = await fetchPromise;
  if (fresh) return fresh;
  notifyOffline();
  return offlineApiFallback();
}

async function networkOnly(req) {
  try {
    return await fetch(req);
  } catch (err) {
    notifyOffline();
    return offlineApiFallback();
  }
}

// --- fetch router ----------------------------------------------------------

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' && req.method !== 'POST') return;
  const url = new URL(req.url);
  // Pass through CROSS-ORIGIN requests entirely. The path-only routing
  // below would otherwise match /api/v1/... on the backend's origin
  // (voice-matters-n66k.onrender.com) and the SW's fetch() of those can
  // throw on cross-origin POSTs, falsely triggering the "backend offline"
  // toast. Browser CORS + the backend's allow-list handle cross-origin
  // calls correctly when the SW stays out of the way.
  if (url.origin !== self.location.origin) return;
  const path = url.pathname;

  // Write paths: never cache.
  if (req.method === 'POST') {
    if (
      path.match(/\/api\/v1\/conversation\/[^/]+\/(voice|chat|action|feedback)$/) ||
      path === '/api/v1/feedback'
    ) {
      event.respondWith(networkOnly(req));
      return;
    }
    // Other POSTs (rare) -> pass through.
    return;
  }

  // GET routing for /api/v1
  if (path.startsWith('/api/v1/')) {
    // Scheme metadata and apply-steps: 24h cache-first.
    if (/^\/api\/v1\/schemes\/[^/]+\/?$/.test(path) ||
        /^\/api\/v1\/schemes\/[^/]+\/apply-steps$/.test(path)) {
      event.respondWith(cacheFirst(req, SCHEMES_CACHE, SCHEMES_TTL_MS));
      return;
    }
    // Scheme explain (LLM + TTS): 7d cache-first.
    if (/^\/api\/v1\/schemes\/[^/]+\/explain/.test(path)) {
      event.respondWith(cacheFirst(req, SCHEMES_CACHE, EXPLAIN_TTL_MS));
      return;
    }
    // Conversation messages + conversation list + per-message explanation
    // are read-mostly with periodic writes -> stale-while-revalidate.
    if (/^\/api\/v1\/conversation\/[^/]+\/messages$/.test(path) ||
        /^\/api\/v1\/conversations$/.test(path) ||
        /^\/api\/v1\/messages\/[^/]+\/explanation$/.test(path)) {
      event.respondWith(staleWhileRevalidate(req, MESSAGES_CACHE));
      return;
    }
    // Anything else under /api/v1 -> network-only.
    event.respondWith(networkOnly(req));
    return;
  }

  // Backend-served audio - cache-first with the long TTL.
  if (path.startsWith('/static/audio/')) {
    event.respondWith(cacheFirst(req, AUDIO_CACHE, EXPLAIN_TTL_MS));
    return;
  }

  // Static frontend assets (precached) - cache-first, network fallback.
  event.respondWith(
    caches.match(req).then(cached => {
      if (cached) return cached;
      return fetch(req).then(res => {
        if (res && res.ok && (res.type === 'basic' || res.type === 'cors')) {
          const copy = res.clone();
          caches.open(STATIC_CACHE).then(c => c.put(req, copy));
        }
        return res;
      }).catch(() => cached);
    })
  );
});
