/**
 * Store 层:localStorage 封装(技术方案 §3.1)
 * - 单一命名空间键 finrookie:v1,值为一个 JSON 对象
 * - 所有读操作容错:JSON.parse 失败 / 键缺失 → 返回默认值(不崩)
 * - 写满 QuotaExceededError → 清 events 缓冲后重试
 */
const STORAGE_KEY = 'finrookie:v1';

let _syncHook = null;
function triggerSync() {
  // 懒加载 sync,避免与 store 的模块循环;未登录时 schedulePush 内部自会跳过
  if (_syncHook) { _syncHook(); return; }
  import('./sync.js').then((m) => { _syncHook = m.schedulePush; _syncHook(); }).catch(() => {});
}

const DEFAULT_STATE = {
  schemaVersion: 1,
  user: {
    tags: { identity: 'other', level: 'L1', interests: ['basics'] },
    onboardedAt: null,
    skippedOnboarding: false,
  },
  progress: {
    streak: 0,
    lastCheckIn: null,
    seenCardIds: [],
    quizStats: { attempts: 0, correct: 0 },
    viewedArticleIds: [],
  },
  difficulty: { current: 'L1', consecutiveWrong: 0 },
  review: [],
  favorites: { cards: [], terms: [] },
  events: [],
};

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

function readRoot() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return deepClone(DEFAULT_STATE);
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || parsed.schemaVersion !== 1) {
      return deepClone(DEFAULT_STATE);
    }
    return parsed;
  } catch (e) {
    console.warn('[store] read failed, fallback to default:', e);
    return deepClone(DEFAULT_STATE);
  }
}

function writeRoot(root) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(root));
    return true;
  } catch (e) {
    if (e && e.name === 'QuotaExceededError') {
      root.events = [];
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(root));
        return true;
      } catch (e2) {
        console.error('[store] write failed after clearing events:', e2);
        return false;
      }
    }
    console.error('[store] write failed:', e);
    return false;
  }
}

function getByPath(obj, path) {
  return path.split('.').reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
}

function setByPath(obj, path, value) {
  const keys = path.split('.');
  const last = keys.pop();
  const target = keys.reduce((acc, key) => {
    if (acc[key] == null || typeof acc[key] !== 'object') acc[key] = {};
    return acc[key];
  }, obj);
  target[last] = value;
}

export const store = {
  /** 读取整棵状态树(容错) */
  getState() {
    return readRoot();
  },
  /** 按点路径读取,缺失/坏值返回 fallback */
  get(path, fallback = undefined) {
    const val = getByPath(readRoot(), path);
    return val === undefined ? fallback : val;
  },
  /** 按点路径写入并持久化 */
  set(path, value) {
    const root = readRoot();
    setByPath(root, path, value);
    const ok = writeRoot(root);
    if (ok) triggerSync();
    return ok;
  },
  /** 以函数方式原子更新整棵树 */
  update(mutator) {
    const root = readRoot();
    mutator(root);
    const ok = writeRoot(root);
    if (ok) triggerSync();
    return ok;
  },
  /** 本地埋点:仅写入 events 缓冲,不外发(技术方案 §7) */
  track(type, payload = {}) {
    const root = readRoot();
    if (!Array.isArray(root.events)) root.events = [];
    root.events.push({ type, payload, at: new Date().toISOString() });
    if (root.events.length > 200) root.events = root.events.slice(-200);
    writeRoot(root);
  },
  reset() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      /* ignore */
    }
  },
  DEFAULT_STATE,
};
