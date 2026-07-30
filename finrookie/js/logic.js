/**
 * 逻辑层:核心算法纯函数(技术方案 §4)
 * 全部为纯函数,便于手工/console 验证,不直接读写 localStorage。
 */

/** §4.1 自陈 → 标签映射(纯查表) */
const LEVEL_MAP = { none: 'L1', little: 'L2', some: 'L3' };

export function mapOnboardingToTags({ identity, level, interests }) {
  return {
    identity: ['student', 'worker', 'other'].includes(identity) ? identity : 'other',
    level: LEVEL_MAP[level] || 'L1',
    interests: Array.isArray(interests) && interests.length ? interests : ['basics'],
  };
}

export const DEFAULT_TAGS = { identity: 'other', level: 'L1', interests: ['basics'] };

/** 难度档位序 */
const LEVELS = ['L1', 'L2', 'L3'];
const levelIndex = (l) => Math.max(0, LEVELS.indexOf(l));

/**
 * §4.2 知识卡匹配 + 三级降级(永不空屏)
 * @returns {{card: object|null, reason: string}}
 *   reason: matched | relax_difficulty | relax_interest | any_unseen | review_mode | empty
 */
export function pickTodayCard(cards, { seenCardIds = [], interests = [], currentLevel = 'L1' }) {
  if (!Array.isArray(cards) || cards.length === 0) {
    return { card: null, reason: 'empty' };
  }
  const seen = new Set(seenCardIds);
  const unseen = cards.filter((c) => !seen.has(c.id));

  const hitsInterest = (c) =>
    Array.isArray(c.topics) && c.topics.some((t) => interests.includes(t));

  // 1) 难度对齐 + 命中兴趣
  let pool = unseen.filter((c) => c.difficulty === currentLevel && hitsInterest(c));
  if (pool.length) return { card: rankByInterest(pool, interests)[0], reason: 'matched' };

  // 2) 放宽难度 ±1 档,仍要求命中兴趣
  const near = new Set(
    [levelIndex(currentLevel) - 1, levelIndex(currentLevel), levelIndex(currentLevel) + 1]
      .filter((i) => i >= 0 && i < LEVELS.length)
      .map((i) => LEVELS[i])
  );
  pool = unseen.filter((c) => near.has(c.difficulty) && hitsInterest(c));
  if (pool.length) return { card: rankByInterest(pool, interests)[0], reason: 'relax_difficulty' };

  // 3) 放宽兴趣:任意未学卡(热门通用兜底)
  if (unseen.length) return { card: unseen[0], reason: 'relax_interest' };

  // 4) 全部学完 → 复习模式(交给上层从 review/收藏取)
  return { card: null, reason: 'review_mode' };
}

/** 兴趣重合度排序:命中标签数多者优先 */
function rankByInterest(pool, interests) {
  return [...pool].sort((a, b) => interestScore(b, interests) - interestScore(a, interests));
}
function interestScore(card, interests) {
  if (!Array.isArray(card.topics)) return 0;
  return card.topics.filter((t) => interests.includes(t)).length;
}

/**
 * §4.3 本地难度微调(替代服务端分层,不回传)
 * @param diff  {current, consecutiveWrong}
 * @param isCorrect 本次是否答对
 * @param recentCorrectRate 近若干题正确率(0~1),用于升档判定
 * @returns {next: {current, consecutiveWrong}, changed: 'up'|'down'|null}
 */
export function adjustDifficulty(diff, isCorrect, recentCorrectRate) {
  const next = { current: diff.current, consecutiveWrong: diff.consecutiveWrong };
  let changed = null;
  if (isCorrect) {
    next.consecutiveWrong = 0;
    if (recentCorrectRate > 0.75 && levelIndex(next.current) < LEVELS.length - 1) {
      next.current = LEVELS[levelIndex(next.current) + 1];
      changed = 'up';
    }
  } else {
    next.consecutiveWrong = diff.consecutiveWrong + 1;
    if (next.consecutiveWrong >= 2 && levelIndex(next.current) > 0) {
      next.current = LEVELS[levelIndex(next.current) - 1];
      next.consecutiveWrong = 0;
      changed = 'down';
    }
  }
  return { next, changed };
}

/**
 * §4.4 连续打卡(幂等 + 断签重置)
 * @param progress {streak, lastCheckIn}
 * @param today 'YYYY-MM-DD'
 * @param yesterday 'YYYY-MM-DD'
 */
export function checkIn(progress, today, yesterday) {
  if (progress.lastCheckIn === today) {
    return { streak: progress.streak, lastCheckIn: today, changed: false };
  }
  let streak;
  if (progress.lastCheckIn === yesterday) streak = progress.streak + 1;
  else streak = 1;
  return { streak, lastCheckIn: today, changed: true };
}

/** 日期工具:本地时区 YYYY-MM-DD */
export function ymd(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}
