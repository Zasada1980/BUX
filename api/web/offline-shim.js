const OFFLINE_SHIM_FLAG = '__sparkOfflineShimInstalled';
const KV_STORAGE_KEY = '__spark_offline_kv__';
const BANNER_ID = 'offline-shim-banner';
const BANNER_STYLE_ID = 'offline-shim-banner-style';

(function () {
    if (typeof window === 'undefined' || window[OFFLINE_SHIM_FLAG]) {
        return;
    }
    window[OFFLINE_SHIM_FLAG] = true;
    const locationProto = window.location?.protocol;
    const search = typeof window.location === 'object' ? window.location.search || '' : '';
    const forcedOffline = Boolean(window.__SPARK_FORCE_OFFLINE) || /(^|&)sparkOffline=1/.test(search) || /(^|&)offline=1/.test(search);
    const shouldShim = locationProto === 'file:' || forcedOffline;
    if (!shouldShim) {
        return;
    }
    const reasonLabel = locationProto === 'file:' ? 'file:// launch' : 'manual override';
    injectBannerStyles();
    showOfflineBanner('Offline mode active (' + reasonLabel + ')');

    const originalFetch = typeof window.fetch === 'function' ? window.fetch.bind(window) : null;
    const kvStores = new Map();
    let hasStorage = false;
    try {
        const testKey = '__spark_offline_test__';
        window.localStorage?.setItem(testKey, '1');
        window.localStorage?.removeItem(testKey);
        hasStorage = true;
    } catch (error) {
        hasStorage = false;
    }

    const safeParse = (value) => {
        if (!value) {
            return {};
        }
        try {
            const parsed = JSON.parse(value);
            return typeof parsed === 'object' && parsed ? parsed : {};
        } catch (error) {
            console.warn('[offline] failed to parse KV cache', error);
            return {};
        }
    };

    if (hasStorage) {
        const snapshot = safeParse(window.localStorage.getItem(KV_STORAGE_KEY));
        Object.keys(snapshot).forEach((bucket) => {
            const store = new Map(Object.entries(snapshot[bucket] || {}));
            kvStores.set(bucket, store);
        });
    }

    const persistKv = () => {
        if (!hasStorage) {
            return;
        }
        const payload = {};
        kvStores.forEach((store, bucket) => {
            payload[bucket] = Object.fromEntries(store.entries());
        });
        try {
            window.localStorage.setItem(KV_STORAGE_KEY, JSON.stringify(payload));
        } catch (error) {
            console.warn('[offline] cannot persist KV cache', error);
        }
    };

    const normalizeUrl = (resource) => {
        try {
            if (typeof resource === 'string') {
                return new URL(resource, 'https://offline.local');
            }
            if (typeof Request !== 'undefined' && resource instanceof Request) {
                return new URL(resource.url);
            }
            if (resource && typeof resource.url === 'string') {
                const base = resource.url.startsWith('/') ? 'https://offline.local' : undefined;
                return new URL(resource.url, base);
            }
        } catch (error) {
            return null;
        }
        return null;
    };

    const resolveMethod = (resource, init) => {
        if (resource && typeof resource.method === 'string') {
            return resource.method;
        }
        if (init && typeof init.method === 'string') {
            return init.method;
        }
        return 'GET';
    };

    const getStore = (collection) => {
        const bucket = collection || 'default';
        if (!kvStores.has(bucket)) {
            kvStores.set(bucket, new Map());
        }
        return kvStores.get(bucket);
    };

    const textResponse = (text, status = 200, contentType = 'text/plain') =>
        Promise.resolve(new Response(text, { status, headers: { 'Content-Type': contentType } }));

    const jsonResponse = (payload, status = 200) => {
        const body = typeof payload === 'string' ? payload : JSON.stringify(payload);
        return textResponse(body, status, 'application/json');
    };

    window.fetch = function (resource, init = {}) {
        const target = normalizeUrl(resource);
        if (target && target.pathname.startsWith('/_spark')) {
            const method = resolveMethod(resource, init).toUpperCase();
            return handleSparkRequest(target, method, init);
        }
        if (originalFetch) {
            return originalFetch(resource, init);
        }
        return Promise.reject(new Error('Fetch недоступен в офлайн-режиме.'));
    };

    const offlineUser = {
        login: 'offline-user',
        name: 'Offline Mode',
        email: 'offline@example.com',
        offline: true
    };

    function handleSparkRequest(url, method, init) {
        const path = url.pathname.slice('/_spark'.length) || '/';
        const collection = url.searchParams.get('collection') || 'default';

        if (path === '/kv' || path === '/kv/') {
            return jsonResponse(Array.from(getStore(collection).keys()));
        }

        if (path.startsWith('/kv/')) {
            const key = decodeURIComponent(path.slice('/kv/'.length));
            const store = getStore(collection);
            if (method === 'GET') {
                if (!store.has(key)) {
                    return textResponse('Not Found', 404);
                }
                return textResponse(store.get(key));
            }
            if (method === 'POST') {
                const body = typeof init.body === 'string' ? init.body : JSON.stringify(init.body || null);
                store.set(key, body);
                persistKv();
                return textResponse('OK');
            }
            if (method === 'DELETE') {
                store.delete(key);
                persistKv();
                return textResponse('OK');
            }
        }

        if (path === '/user') {
            return jsonResponse({ ...offlineUser, updatedAt: new Date().toISOString(), source: 'offline-shim' });
        }

        if (path === '/loaded' || path === '/status') {
            return jsonResponse({
                status: 'offline',
                reason: reasonLabel,
                timestamp: new Date().toISOString(),
                source: 'offline-shim'
            });
        }

        if (path === '/llm') {
            const body = typeof init.body === 'string' ? init.body : JSON.stringify(init.body || {});
            return jsonResponse({
                id: 'offline-llm',
                model: 'offline/local',
                created: Date.now(),
                offline: true,
                choices: [
                    { message: { role: 'assistant', content: '\u26A0\uFE0F Offline: LLM unavailable. Request preview: ' + truncatePreview(body) } }
                ]
            });
        }

        return jsonResponse({ ok: true, source: 'offline-shim', timestamp: new Date().toISOString() });
    }

    function truncatePreview(body) {
        if (!body) {
            return 'нет данных';
        }
        try {
            const parsed = JSON.parse(body);
            const messages = Array.isArray(parsed.messages) ? parsed.messages : [];
            const userMessage = [...messages].reverse().find((msg) => msg?.role === 'user');
            const content = userMessage?.content;
            if (typeof content === 'string') {
                return clip(content);
            }
            if (content) {
                return clip(JSON.stringify(content));
            }
        } catch (error) {
            return clip(body);
        }
        return 'нет данных';
    }

    function clip(value) {
        const normalized = value.replace(/\s+/g, ' ').trim();
        return normalized.length > 100 ? normalized.slice(0, 97) + '...' : normalized;
    }
})();

function injectBannerStyles() {
    if (document.getElementById(BANNER_STYLE_ID)) {
        return;
    }
    const style = document.createElement('style');
    style.id = BANNER_STYLE_ID;
    style.textContent = '\n.offline-banner { position: fixed; top: 0; left: 0; right: 0; padding: 0.65rem 1rem; background: linear-gradient(90deg, #f43f5e, #fb923c); color: #fff; font-size: 0.9rem; text-align: center; z-index: 2147484000; box-shadow: 0 12px 24px rgba(15,23,42,0.3); display: flex; align-items: center; justify-content: center; gap: 0.35rem; }\n.offline-banner button { background: transparent; border: 1px solid rgba(255,255,255,0.6); color: #fff; border-radius: 999px; padding: 0.2rem 0.75rem; cursor: pointer; font-size: 0.85rem; }';
    document.head.appendChild(style);
}

function showOfflineBanner(message) {
    if (!document.body) {
        return;
    }
    let banner = document.getElementById(BANNER_ID);
    if (!banner) {
        banner = document.createElement('div');
        banner.id = BANNER_ID;
        banner.className = 'offline-banner';
        const text = document.createElement('span');
        text.textContent = message;
        const close = document.createElement('button');
        close.textContent = 'Скрыть';
        close.onclick = () => banner.remove();
        banner.appendChild(text);
        banner.appendChild(close);
        document.body.appendChild(banner);
    } else {
        banner.firstElementChild.textContent = message;
    }
}
