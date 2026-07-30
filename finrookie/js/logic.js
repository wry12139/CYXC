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

/** 兴趣主题中文名(展示用) */
export const TOPIC_LABELS = {
  basics: '理财基础',
  fund: '基金',
  stock: '股票',
  avoid_pit: '避坑',
  insurance: '保险',
};

/**
 * §② 数据聚合:把散落的答题/学习行为加工成一张学习画像(纯函数)
 * @param {Array} events    本地埋点 events[](含 quiz_answer / card_view)
 * @param {Array} cards     知识卡库
 * @param {Array} quiz      题库
 * @param {Array} review    复习池
 * @param {object} tags     用户标签 {interests:[], level}
 * @returns {{
 *   totalAttempts:number, totalCorrect:number, overallRate:number,
 *   topics: Array<{topic,label,attempts,correct,rate,seenCards}>,
 *   weakestTopic: object|null, strongestTopic: object|null,
 *   pendingReview:number, seenCardCount:number
 * }}
 */
export function analyzeMastery(events, cards, quiz, review, tags) {
  const evs = Array.isArray(events) ? events : [];
  const cardList = Array.isArray(cards) ? cards : [];
  const quizList = Array.isArray(quiz) ? quiz : [];
  const reviewList = Array.isArray(review) ? review : [];
  const interests = (tags && Array.isArray(tags.interests) && tags.interests.length)
    ? tags.interests
    : Object.keys(TOPIC_LABELS);

  const quizById = new Map(quizList.map((q) => [q.id, q]));
  const cardById = new Map(cardList.map((c) => [c.id, c]));

  // 按主题聚合答题正确率:answer → quiz → card → topics
  const topicStat = {}; // topic -> {attempts, correct}
  interests.forEach((t) => (topicStat[t] = { attempts: 0, correct: 0 }));

  let totalAttempts = 0;
  let totalCorrect = 0;

  evs.forEach((e) => {
    if (e.type !== 'quiz_answer' || !e.payload) return;
    totalAttempts += 1;
    const isCorrect = !!e.payload.correct;
    if (isCorrect) totalCorrect += 1;
    const q = quizById.get(e.payload.quizId);
    if (!q) return;
    const card = cardById.get(q.cardId);
    if (!card || !Array.isArray(card.topics)) return;
    card.topics.forEach((t) => {
      if (!topicStat[t]) topicStat[t] = { attempts: 0, correct: 0 };
      topicStat[t].attempts += 1;
      if (isCorrect) topicStat[t].correct += 1;
    });
  });

  // 已学卡按主题计数(seenCards),从 card_view 事件去重取卡
  const seenCardIds = new Set(
    evs.filter((e) => e.type === 'card_view' && e.payload).map((e) => e.payload.cardId)
  );
  const seenByTopic = {};
  seenCardIds.forEach((cid) => {
    const card = cardById.get(cid);
    if (!card || !Array.isArray(card.topics)) return;
    card.topics.forEach((t) => (seenByTopic[t] = (seenByTopic[t] || 0) + 1));
  });

  const topics = Object.keys(topicStat).map((t) => {
    const { attempts, correct } = topicStat[t];
    return {
      topic: t,
      label: TOPIC_LABELS[t] || t,
      attempts,
      correct,
      rate: attempts ? correct / attempts : null, // 无数据为 null,区别于 0%
      seenCards: seenByTopic[t] || 0,
    };
  });

  // 最弱/最强主题:仅在有答题记录的主题里比较
  const answered = topics.filter((t) => t.attempts > 0);
  answered.sort((a, b) => a.rate - b.rate);
  const weakestTopic = answered.length ? answered[0] : null;
  const strongestTopic = answered.length ? answered[answered.length - 1] : null;

  return {
    totalAttempts,
    totalCorrect,
    overallRate: totalAttempts ? totalCorrect / totalAttempts : null,
    topics,
    weakestTopic,
    strongestTopic,
    pendingReview: reviewList.filter((r) => !r.cleared).length,
    seenCardCount: seenCardIds.size,
  };
}

/**
 * §③ 建议生成:把学习画像翻译成 2-3 条自然语言建议(纯函数,规则引擎)
 * @param {object} mastery  analyzeMastery 的输出
 * @param {object} difficulty {current, consecutiveWrong}
 * @param {number} streak    连续打卡天数
 * @returns {Array<{type:'praise'|'suggest'|'warn'|'guide', text:string}>}
 */
export function generateInsights(mastery, difficulty, streak) {
  const insights = [];
  const m = mastery || {};
  const level = (difficulty && difficulty.current) || 'L1';
  const levelName = { L1: '萌新', L2: '入门', L3: '进阶' }[level] || level;

  // 冷启动:还没答过题
  if (!m.totalAttempts) {
    insights.push({
      type: 'guide',
      text: '还没做过测验哦。学完知识卡点「测一测」,我就能帮你分析掌握情况啦。',
    });
    return insights;
  }

  // 1) 总体表现点评
  const rate = m.overallRate;
  if (rate >= 0.8) {
    insights.push({
      type: 'praise',
      text: `总体正确率 ${Math.round(rate * 100)}%,基础很扎实!当前处于「${levelName}」档,可以挑战更难的内容。`,
    });
  } else if (rate >= 0.5) {
    insights.push({
      type: 'suggest',
      text: `总体正确率 ${Math.round(rate * 100)}%,稳步前进中。多复习错题能更快提升。`,
    });
  } else {
    insights.push({
      type: 'warn',
      text: `总体正确率 ${Math.round(rate * 100)}%,别气馁——先把「${levelName}」档的基础卡吃透,难度会自动帮你调节。`,
    });
  }

  // 2) 主题强弱对比(有明显差距才提)
  const weak = m.weakestTopic;
  const strong = m.strongestTopic;
  if (weak && strong && weak.topic !== strong.topic && weak.rate < 0.6) {
    insights.push({
      type: 'suggest',
      text: `你在「${strong.label}」表现最好(${Math.round(strong.rate * 100)}%),但「${weak.label}」偏弱(${Math.round(weak.rate * 100)}%),建议优先补一补「${weak.label}」。`,
    });
  } else if (weak && weak.rate < 0.5) {
    insights.push({
      type: 'suggest',
      text: `「${weak.label}」正确率偏低(${Math.round(weak.rate * 100)}%),可以在「今日」多刷几张这个主题的卡。`,
    });
  }

  // 3) 复习池提醒
  if (m.pendingReview >= 3) {
    insights.push({
      type: 'warn',
      text: `有 ${m.pendingReview} 道错题待复习,趁热打铁去「待复习错题」重做一遍吧。`,
    });
  } else if (m.pendingReview > 0) {
    insights.push({
      type: 'suggest',
      text: `还有 ${m.pendingReview} 道错题没消化,重做通关就能移出复习池。`,
    });
  }

  // 4) 打卡鼓励(仅在前面建议不足 3 条时补充,避免刷屏)
  if (insights.length < 3 && streak >= 3) {
    insights.push({
      type: 'praise',
      text: `已连续打卡 ${streak} 天,坚持就是复利,继续保持!`,
    });
  }

  return insights.slice(0, 3); // 最多 3 条,避免信息过载
}
