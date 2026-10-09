/**
 * BillFlow Pro - Service Worker
 * Supports: Android, iOS, Windows, Mac, Desktop
 * Strategy: Network-first with offline fallback
 */

const CACHE_NAME = 'billflow-v2';
const STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/js/main.js',
  '/manifest.json',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
];

// Install - cache static assets
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS.filter(Boolean)).catch(() => {});
    })
  );
});

// Activate - clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => clients.claim())
  );
});

// Fetch - Network first, cache fallback
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  
  const url = new URL(event.request.url);
  
  // Don't intercept API calls or auth routes
  if (url.pathname.startsWith('/login') || 
      url.pathname.startsWith('/logout') ||
      url.pathname.startsWith('/api/') ||
      url.pathname.includes('csrf')) {
    return;
  }

  // Cache-first for static assets
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => cached || new Response('', { status: 408 }));
      })
    );
    return;
  }

  // Network first for pages
  event.respondWith(
    fetch(event.request).catch(() => {
      return caches.match(event.request);
    })
  );
});
