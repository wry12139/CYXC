// js/ai.js
// AI 名词科普兜底:调独立 AI 服务(8092)。Key 只在后端,前端只传 token。
const AI_BASE = 'http://10.159.3.80:8092';
const TIMEOUT_MS = 22000;

export async function askAI(question, token) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${AI_BASE}/api/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const err = new Error(`HTTP ${res.status}`);
      err.code = `HTTP_${res.status}`;
      throw err;
    }
    return await res.json();
  } catch (e) {
    if (e.name === 'AbortError') { e.code = 'TIMEOUT'; }
    e.code = e.code || 'FETCH_FAILED';
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
