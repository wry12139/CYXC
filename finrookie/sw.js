/**
 * Service Worker:PWA 离线缓存(技术方案 §10)
 * - 静态壳(HTML/JS/图标/CDN):cache-first,安装即缓存,离线可开
 * - 内容 JSON(data/*):network-first → 失败回退缓存,兼顾更新与离线
 * - 版本号控制更新:改 CACHE_VERSION 即可让旧缓存整体失效
 */
const CACHE_VERSION = 'finrookie-v12';
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './js/app.js',
  './js/store.js',
  './js/repository.js',
  './js/logic.js',
  './js/auth.js',
  './js/sync.js',
  './js/merge.js',
  './assets/icon-192.png',
  './assets/icon-512.png',
  // 内容种子:预缓存保证「首次安装后立即断网」也有内容可读(修复 P1-01)
  './data/knowledge-cards.json',
  './data/quiz.json',
  './data/glossary.json',
  './data/articles.json',
  'https://cdn.tailwindcss.com',
  'https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) =>
      // 逐个 add,单个 CDN 失败不阻断整体安装
      Promise.allSettled(APP_SHELL.map((url) => cache.add(url)))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const isContent = url.pathname.includes('/data/');

  if (isContent) {
    // 内容 JSON:network-first,离线回退缓存
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req))
    );
  } else {
    // 静态壳:cache-first,未命中再走网络并回填
    event.respondWith(
      caches.match(req).then((cached) =>
        cached ||
        fetch(req).then((res) => {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(req, copy));
          return res;
        })
      )
    );
  }
});
