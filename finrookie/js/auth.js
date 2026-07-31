// js/auth.js
// 后端地址:局域网服务器。本地联调时可临时改为 http://127.0.0.1:8091
export const API_BASE = 'http://10.159.3.80:8091';

const TOKEN_KEY = 'finrookie:token';
const NAME_KEY = 'finrookie:username';

export function getToken() { return localStorage.getItem(TOKEN_KEY); }
export function getUsername() { return localStorage.getItem(NAME_KEY); }
export function isLoggedIn() { return !!getToken(); }

async function postJSON(path, body, withAuth = false) {
  const headers = { 'Content-Type': 'application/json' };
  if (withAuth) {
    const t = getToken();
    if (t) headers['Authorization'] = `Bearer ${t}`;
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST', headers, body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (_) {}
    return { status: res.status, data };
  } catch (_) {
    return { status: 0, data: { error: 'network_error' } };
  }
}

export async function register(username, password) {
  const { status, data } = await postJSON('/api/register', { username, password });
  if (status === 201) return { ok: true };
  return { error: data.error || 'register_failed' };
}

export async function login(username, password) {
  const { status, data } = await postJSON('/api/login', { username, password });
  if (status === 200 && data.token) {
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(NAME_KEY, data.username || username);
    return { ok: true, username: data.username || username };
  }
  return { error: data.error || 'login_failed' };
}

export async function logout() {
  try { await postJSON('/api/logout', {}, true); } catch (_) {}
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(NAME_KEY);
}
