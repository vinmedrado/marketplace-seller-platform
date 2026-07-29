/* MarketPlace Seller Platform PATCH 15.1 FINAL — PWA real seguro */
const VERSION = '15.1.0';
const STATIC_CACHE = `marketplace-seller-platform-static-${VERSION}`;
const RUNTIME_CACHE = `marketplace-seller-platform-runtime-${VERSION}`;
const OFFLINE_URL = '/offline.html';
const APP_SHELL = ['/', '/index.html', OFFLINE_URL, '/manifest.json'];
const SENSITIVE_PATTERNS = [
  /\/auth(\/|$)/i,
  /\/oauth(\/|$)/i,
  /\/billing(\/|$)/i,
  /\/webhook/i,
  /\/pagarme/i,
  /access_token/i,
  /refresh_token/i,
  /code=/i,
  /authorization/i,
  /\/marketplace\/connect/i,
  /\/marketplace\/oauth/i,
  /\/finance-reconciliation/i,
  /\/system\/status/i
];
const SAFE_PUBLIC_API = [/\/sites\/MLB\/search/i];
function isSensitive(req, url) {
  if (req.method !== 'GET') return true;
  if (req.headers.has('authorization')) return true;
  const full = `${url.pathname}${url.search}`;
  return SENSITIVE_PATTERNS.some((rx) => rx.test(full));
}
function isStaticAsset(url) {
  return url.origin === self.location.origin && (
    url.pathname.startsWith('/assets/') ||
    url.pathname.startsWith('/icons/') ||
    /\.(css|js|svg|png|jpg|jpeg|webp|woff2?)$/i.test(url.pathname)
  );
}
async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  const res = await fetch(req);
  if (res && res.ok) {
    const cache = await caches.open(STATIC_CACHE);
    cache.put(req, res.clone());
  }
  return res;
}
async function networkFirst(req, cacheName, timeoutMs = 3500) {
  const cache = await caches.open(cacheName);
  const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('network-timeout')), timeoutMs));
  try {
    const res = await Promise.race([fetch(req), timeout]);
    if (res && res.ok && res.type !== 'opaque') cache.put(req, res.clone());
    return res;
  } catch (err) {
    const cached = await cache.match(req);
    if (cached) return cached;
    throw err;
  }
}
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => ![STATIC_CACHE, RUNTIME_CACHE].includes(key)).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) {
    if (SAFE_PUBLIC_API.some((rx) => rx.test(url.href))) event.respondWith(networkFirst(req, RUNTIME_CACHE, 2500));
    return;
  }
  if (isSensitive(req, url)) return;
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(STATIC_CACHE).then((cache) => cache.put('/index.html', copy));
      return res;
    }).catch(async () => (await caches.match('/index.html')) || caches.match(OFFLINE_URL)));
    return;
  }
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(req).catch(() => caches.match(req)));
    return;
  }
  if (url.pathname.startsWith('/api/public/')) {
    event.respondWith(networkFirst(req, RUNTIME_CACHE, 2500));
  }
});
