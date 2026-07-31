// js/sync.js
import { API_BASE, getToken, logout } from './auth.js';
import { mergeState } from './merge.js';
import { store } from './store.js';

async function authedFetch(path, options = {}) {
  const token = getToken();
  if (!token) return { status: 401, data: {} };
  const headers = { ...(options.headers || {}), 'Authorization': `Bearer ${token}` };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  return { status: res.status, data };
}

export async function pushNow() {
  if (!getToken()) return { error: 'not_logged_in' };
  const state = store.getState();
  const { status } = await authedFetch('/api/sync/push', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: state }),
  });
  if (status === 401) { await logout(); return { error: 'unauthorized' }; }
  if (status === 200) return { ok: true };
  return { error: 'push_failed' };
}

export async function pullAndMerge() {
  if (!getToken()) return { error: 'not_logged_in' };
  const { status, data } = await authedFetch('/api/sync/pull', { method: 'GET' });
  if (status === 401) { await logout(); return { error: 'unauthorized' }; }
  if (status !== 200) return { error: 'pull_failed' };
  if (data.data) {
    const local = store.getState();
    const merged = mergeState(local, data.data);
    store.update((root) => { Object.assign(root, merged); });
    await pushNow(); // 把合并结果回推,使云端与本地一致
    return { ok: true, merged };
  }
  // 云端还没有该用户数据:把本地现状推上去
  await pushNow();
  return { ok: true };
}

let _pushTimer = null;
export function schedulePush() {
  if (!getToken()) return;
  clearTimeout(_pushTimer);
  _pushTimer = setTimeout(() => { pushNow().catch(() => {}); }, 2000);
}
