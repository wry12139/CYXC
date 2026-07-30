/**
 * Repository 层:内容读取抽象(技术方案 §11 接口预留)
 * 阶段一实现 = 读静态 JSON;阶段二换实现为调 API,UI/逻辑层不改。
 * 内置超时与错误抛出,供上层做降级(§6)。
 */

const DATA_BASE = './data';
const TIMEOUT_MS = 2000; // PRD 性能:加载 ≤2s,超时走骨架屏重试

async function fetchJSON(url, { timeout = TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, { signal: controller.signal, cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    return await res.json();
  } catch (e) {
    if (e.name === 'AbortError') {
      const err = new Error(`timeout after ${timeout}ms: ${url}`);
      err.code = 'TIMEOUT';
      throw err;
    }
    e.code = e.code || 'FETCH_FAILED';
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export const repository = {
  async getCards() {
    return fetchJSON(`${DATA_BASE}/knowledge-cards.json`);
  },
  async getQuiz() {
    return fetchJSON(`${DATA_BASE}/quiz.json`);
  },
  async getGlossary() {
    return fetchJSON(`${DATA_BASE}/glossary.json`);
  },
  async getBriefing(dateStr) {
    return fetchJSON(`${DATA_BASE}/briefings/${dateStr}.json`);
  },
};
