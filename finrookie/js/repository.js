/**
 * Repository 层:内容读取抽象(技术方案 §11 接口预留)
 * 阶段一实现 = 读静态 JSON;阶段二换实现为调 API,UI/逻辑层不改。
 * 内置超时与错误抛出,供上层做降级(§6)。
 */

const DATA_BASE = './data';
const API_BASE = 'http://10.159.3.80:8091';
const TIMEOUT_MS = 2000; // PRD 性能:加载 ≤2s,超时走骨架屏重试
const CONTENT_TYPE_MAP = {
  knowledge_card: 'knowledge-cards.json',
  quiz: 'quiz.json',
  glossary: 'glossary.json',
  article: 'articles.json',
};

async function fetchJSON(url, { timeout = TIMEOUT_MS, headers = {} } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, { signal: controller.signal, cache: 'no-cache', headers });
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

async function loadSeedData(type) {
  const filename = CONTENT_TYPE_MAP[type];
  if (!filename) throw new Error(`unsupported content type: ${type}`);
  return fetchJSON(`${DATA_BASE}/${filename}`);
}

async function getContentByType(type) {
  try {
    return await fetchJSON(`/api/content?type=${encodeURIComponent(type)}`);
  } catch (e) {
    console.warn(`[content] api load failed for ${type}, fallback to seed:`, e.message);
    return loadSeedData(type);
  }
}

export const repository = {
  loadSeedData,
  getContentByType,
  async getCards() {
    return getContentByType('knowledge_card');
  },
  async getQuiz() {
    return getContentByType('quiz');
  },
  async getGlossary() {
    return getContentByType('glossary');
  },
  async getArticles() {
    return getContentByType('article');
  },
  async getRecommendations(num = 3) {
    return fetchJSON(`/api/recommendations?num=${encodeURIComponent(num)}`);
  },
  async getBriefing(dateStr) {
    return fetchJSON(`${DATA_BASE}/briefings/${dateStr}.json`);
  },
  async getRecommendations(token, num = 5) {
    if (!token) return [];
    try {
      return await fetchJSON(`${API_BASE}/api/recommendations?num=${num}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        timeout: 3000
      });
    } catch (e) {
      console.warn('Failed to load recommendations:', e);
      return [];
    }
  }
};
