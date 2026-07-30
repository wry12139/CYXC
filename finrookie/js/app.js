import { store } from './store.js';
import { repository } from './repository.js';
import {
  mapOnboardingToTags,
  DEFAULT_TAGS,
  pickTodayCard,
  adjustDifficulty,
  checkIn,
  ymd,
  analyzeMastery,
  generateInsights,
} from './logic.js';

/** 全局运行时错误兜底:仅对真正的致命 JS 异常提示,过滤跨域/资源噪声(技术方案 §6) */
let errorBannerTimer = null;
function showErrorBanner() {
  const banner = document.getElementById('global-error');
  if (!banner) return;
  banner.classList.remove('hidden');
  // 自动消失:避免无害错误常驻影响观感
  clearTimeout(errorBannerTimer);
  errorBannerTimer = setTimeout(() => banner.classList.add('hidden'), 5000);
}
window.addEventListener('error', (e) => {
  // 资源加载失败(img/script/link 的 error):无 message,不弹横幅
  if (e.target && e.target !== window && e.target.tagName) {
    console.warn('[resource error]', e.target.src || e.target.href);
    return;
  }
  // 跨域脚本抛出的匿名 "Script error."(无 error 对象):浏览器已脱敏,通常无害,不弹
  if (!e.error && (!e.message || e.message === 'Script error.')) {
    console.warn('[script error suppressed]', e.message);
    return;
  }
  console.error('[global error]', e.error || e.message);
  showErrorBanner();
}, true);
window.addEventListener('unhandledrejection', (e) => {
  // 内容加载超时/网络类拒绝已在各自流程处理并有 UI 兜底,这里只记录不弹横幅
  console.error('[unhandled rejection]', e.reason);
});

/** hash 路由:三 Tab + onboarding(技术方案 §2) */
const ROUTES = ['onboarding', 'home', 'briefing', 'me'];
function currentRoute() {
  const hash = (location.hash || '').replace(/^#\//, '');
  return ROUTES.includes(hash) ? hash : null;
}

export function app() {
  return {
    // ---- 状态 ----
    route: 'home',
    loading: true,
    // 内容
    cards: [],
    quiz: [],
    glossary: {},
    // 首页结果区
    todayCard: null,
    cardReason: '',
    // 加载/错误态(§6)
    contentError: null, // {code, retry}
    // 术语弹层
    activeTerm: null,
    activeTermText: '',
    // 测验浮层(F-02)
    quizOpen: false,
    activeQuiz: null,        // 当前题对象
    selectedOption: null,    // 用户选中项 index
    quizAnswered: false,     // 是否已提交判定
    quizIsCorrect: false,    // 本次判定结果
    diffChange: null,        // 'up' | 'down' | null 难度变化提示
    reviewMode: false,       // 当前测验是否来自复习池(F-03)
    // 早报(F-04)
    briefing: null,          // 当前展示的早报对象 {date, disclaimer, items}
    briefingLoading: false,
    briefingError: null,     // {code} 加载失败
    briefingFallback: false, // 是否为回退到最近一期(今日未发布)
    // onboarding 输入区(F-08)
    onboarding: { identity: '', level: '', interests: [] },
    // 用户态镜像(展示用)
    tags: DEFAULT_TAGS,
    streak: 0,

    // ---- 生命周期 ----
    async init() {
      this.tags = store.get('user.tags', DEFAULT_TAGS);
      this.streak = store.get('progress.streak', 0);

      // 路由决策:未 onboard 且未跳过 → 强制引导页
      const onboardedAt = store.get('user.onboardedAt', null);
      const skipped = store.get('user.skippedOnboarding', false);
      const routed = currentRoute();
      if (!onboardedAt && !skipped) {
        this.go('onboarding');
      } else {
        this.route = routed && routed !== 'onboarding' ? routed : 'home';
      }

      window.addEventListener('hashchange', () => {
        const r = currentRoute();
        if (r) this.route = r;
      });

      await this.loadContent();
      if (this.route === 'home') await this.refreshTodayCard();
      if (this.route === 'briefing') await this.loadBriefing();
      if (this.route === 'me') this.refreshMe();
      this.loading = false;
    },

    go(route) {
      location.hash = `#/${route}`;
      this.route = route;
      if (route === 'home' && !this.todayCard && !this.contentError) {
        this.refreshTodayCard();
      }
      if (route === 'briefing' && !this.briefing && !this.briefingError) {
        this.loadBriefing();
      }
      if (route === 'me') {
        this.refreshMe();
      }
    },

    // ---- 内容加载 + 错误兜底(§6, 任务4)----
    async loadContent() {
      this.contentError = null;
      try {
        const [cards, quiz, glossary] = await Promise.all([
          repository.getCards(),
          repository.getQuiz(),
          repository.getGlossary(),
        ]);
        this.cards = Array.isArray(cards) ? cards : [];
        this.quiz = Array.isArray(quiz) ? quiz : [];
        this.glossary = glossary && typeof glossary === 'object' ? glossary : {};
      } catch (e) {
        // 拉取失败/超时:记录错误码,UI 展示占位+重试
        this.contentError = { code: e.code || 'FETCH_FAILED', message: e.message };
        this.cards = this.cards || [];
      }
    },

    async retryContent() {
      this.loading = true;
      await this.loadContent();
      if (!this.contentError && this.route === 'home') await this.refreshTodayCard();
      this.loading = false;
    },

    // ---- 早报加载:今日缺失回退最近一期(F-04, §6)----
    async loadBriefing() {
      this.briefingLoading = true;
      this.briefingError = null;
      this.briefingFallback = false;
      // 从今日往前回溯,最多找 7 天内最近一期
      const base = new Date();
      for (let i = 0; i < 7; i++) {
        const d = new Date(base);
        d.setDate(base.getDate() - i);
        const dateStr = ymd(d);
        try {
          const data = await repository.getBriefing(dateStr);
          if (data && Array.isArray(data.items)) {
            this.briefing = data;
            this.briefingFallback = i > 0; // 非今日 → 回退提示
            this.briefingLoading = false;
            store.track('briefing_open', { date: dateStr, fallback: i > 0 });
            return;
          }
        } catch (e) {
          // 该日无早报(404/超时),继续往前找
          if (e.code === 'TIMEOUT') {
            // 超时视为网络问题,直接报错不再回溯
            this.briefingError = { code: 'TIMEOUT' };
            this.briefingLoading = false;
            return;
          }
        }
      }
      // 7 天内都没有 → 空态
      this.briefingError = { code: 'NO_BRIEFING' };
      this.briefingLoading = false;
    },
    async retryBriefing() {
      this.briefing = null;
      await this.loadBriefing();
    },

    // ---- 首页结果区:出卡 + 三级降级(F-01, 任务3)----
    async refreshTodayCard() {
      if (this.contentError) return;
      const seen = store.get('progress.seenCardIds', []);
      const level = store.get('difficulty.current', 'L1');
      const interests = store.get('user.tags.interests', ['basics']);
      const { card, reason } = pickTodayCard(this.cards, {
        seenCardIds: seen,
        interests,
        currentLevel: level,
      });
      this.todayCard = card;
      this.cardReason = reason;
      if (card) {
        store.track('card_view', { cardId: card.id, reason });
      }
    },

    get cardReasonLabel() {
      const m = {
        matched: '',
        relax_difficulty: '为你调整了难度',
        relax_interest: '猜你也会喜欢',
        review_mode: '',
        empty: '',
      };
      return m[this.cardReason] || '';
    },

    get isEmptyLibrary() {
      return !this.contentError && this.cards.length === 0;
    },
    get isReviewMode() {
      return this.cardReason === 'review_mode';
    },

    markCardSeen() {
      if (!this.todayCard) return;
      const seen = store.get('progress.seenCardIds', []);
      if (!seen.includes(this.todayCard.id)) {
        store.set('progress.seenCardIds', [...seen, this.todayCard.id]);
      }
      this.doCheckIn();
    },

    doCheckIn() {
      const today = ymd(new Date());
      const y = new Date();
      y.setDate(y.getDate() - 1);
      const yesterday = ymd(y);
      const progress = store.get('progress', { streak: 0, lastCheckIn: null });
      const res = checkIn(progress, today, yesterday);
      if (res.changed) {
        store.set('progress.streak', res.streak);
        store.set('progress.lastCheckIn', res.lastCheckIn);
        this.streak = res.streak;
      }
    },

    nextCard() {
      this.markCardSeen();
      this.refreshTodayCard();
    },

    // ---- 收藏(F-03 最小)----
    isFav(cardId) {
      return store.get('favorites.cards', []).includes(cardId);
    },
    toggleFav(cardId) {
      const favs = store.get('favorites.cards', []);
      const next = favs.includes(cardId)
        ? favs.filter((id) => id !== cardId)
        : [...favs, cardId];
      store.set('favorites.cards', next);
      this.refreshMe(); // 同步"我的"页派生列表
    },

    // ---- F-03 我的页:收藏列表 + 复习池 ----
    favCards: [],        // 已收藏的知识卡对象列表(派生)
    reviewItems: [],     // 待复习错题(未 cleared,派生,带题干)
    meExpanded: 'none',  // 展开区:'fav' | 'review' | 'none'
    // 学习报告(②聚合 + ③建议)
    mastery: null,       // analyzeMastery 输出
    insights: [],        // generateInsights 输出

    refreshMe() {
      // 收藏卡:按 favorites.cards 顺序映射到卡对象(过滤已不存在的)
      const favIds = store.get('favorites.cards', []);
      const cardById = new Map(this.cards.map((c) => [c.id, c]));
      this.favCards = favIds.map((id) => cardById.get(id)).filter(Boolean);
      // 复习池:未 cleared 的错题,补上题干供展示
      const review = store.get('review', []);
      const quizById = new Map(this.quiz.map((q) => [q.id, q]));
      this.reviewItems = review
        .filter((r) => !r.cleared)
        .map((r) => ({ ...r, quiz: quizById.get(r.quizId) }))
        .filter((r) => r.quiz);
      // 学习报告:②聚合 → ③建议(纯函数,基于本地数据)
      const events = store.get('events', []);
      const difficulty = store.get('difficulty', { current: 'L1', consecutiveWrong: 0 });
      this.mastery = analyzeMastery(events, this.cards, this.quiz, review, this.tags);
      this.insights = generateInsights(this.mastery, difficulty, this.streak);
    },
    toggleMeSection(section) {
      this.meExpanded = this.meExpanded === section ? 'none' : section;
    },
    // 学习报告展示辅助
    get masteryAnsweredTopics() {
      if (!this.mastery || !Array.isArray(this.mastery.topics)) return [];
      return this.mastery.topics
        .filter((t) => t.attempts > 0)
        .sort((a, b) => a.rate - b.rate);
    },
    get masteryRateColor() {
      const r = this.mastery ? this.mastery.overallRate : null;
      if (r === null || r === undefined) return 'text-slate-400';
      return r >= 0.8 ? 'text-brand' : r >= 0.5 ? 'text-amber' : 'text-red-500';
    },
    get masteryBarColor() {
      const r = this.mastery ? this.mastery.overallRate : null;
      if (r === null || r === undefined) return 'bg-slate-300';
      return r >= 0.8 ? 'bg-brand' : r >= 0.5 ? 'bg-amber' : 'bg-red-400';
    },
    insightBoxClass(type) {
      return {
        praise: 'bg-brand-tint text-brand-dark',
        suggest: 'bg-amber/10 text-amber-dark',
        warn: 'bg-red-50 text-red-600',
        guide: 'bg-slate-100 text-slate-600',
      }[type] || 'bg-slate-100 text-slate-600';
    },
    insightIcon(type) {
      return { praise: '🎉', suggest: '💡', warn: '⚠️', guide: '🧭' }[type] || '💡';
    },
    /** 从复习池发起重做:复用测验浮层,标记 fromReview */
    startReview(item) {
      if (!item || !item.quiz) return;
      this.startQuiz(item.quiz, true);
    },

    /** 建议可点击闭环:把报告建议的 action 翻译成实际导航/动作 */
    handleInsightAction(action) {
      if (!action || !action.type) return;
      store.track('insight_action', { type: action.type, payload: action.payload || null });
      switch (action.type) {
        case 'go_home':
          this.go('home');
          break;
        case 'learn_topic':
          this.learnTopic(action.payload && action.payload.topic);
          break;
        case 'go_review':
          this.go('me');
          this.meExpanded = 'review';
          // 等 Alpine 渲染出展开区再滚动定位
          this.$nextTick(() => {
            const el = document.getElementById('me-review-section');
            if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          });
          break;
      }
    },

    /** 定向出卡:优先取该主题未学卡,兜底任意该主题卡,再兜底走通用出卡 */
    learnTopic(topic) {
      // 先定卡再导航:若 topic 无效直接走常规出卡逻辑
      if (!topic || this.contentError) {
        this.go('home');
        if (!this.todayCard && !this.contentError) this.refreshTodayCard();
        return;
      }
      const seen = new Set(store.get('progress.seenCardIds', []));
      const inTopic = this.cards.filter(
        (c) => Array.isArray(c.topics) && c.topics.includes(topic)
      );
      const pick = inTopic.find((c) => !seen.has(c.id)) || inTopic[0];
      if (pick) {
        // 先落定向卡,再 go('home')——go 的 guard(!todayCard)因此不会触发异步刷新覆盖
        this.todayCard = pick;
        this.cardReason = 'matched';
        store.track('card_view', { cardId: pick.id, reason: 'insight_topic' });
        this.go('home');
      } else {
        // 该主题暂无卡:退回常规出卡,不空屏
        this.go('home');
        this.refreshTodayCard();
      }
    },

    // ---- 术语弹层(F-05 最小,委托点击)----
    handleBodyClick(e) {
      const el = e.target.closest('[data-term]');
      if (!el) return;
      const term = el.getAttribute('data-term');
      this.openTerm(term);
    },
    openTerm(term) {
      this.activeTerm = term;
      this.activeTermText = this.glossary[term] || '暂无解释';
      store.track('term_click', { term });
    },
    closeTerm() {
      this.activeTerm = null;
    },

    // ---- 测验浮层:F-02(答题→判定→解析→难度微调→错题入池)----
    /** 从知识卡打开测验:取该卡关联的第一道未通关题 */
    openQuizForCard(card) {
      if (!card || !Array.isArray(card.quizIds) || !card.quizIds.length) return;
      const quiz = this.quiz.find((q) => card.quizIds.includes(q.id));
      if (!quiz) return;
      this.startQuiz(quiz, false);
    },
    startQuiz(quiz, fromReview = false) {
      this.activeQuiz = quiz;
      this.selectedOption = null;
      this.quizAnswered = false;
      this.quizIsCorrect = false;
      this.diffChange = null;
      this.reviewMode = fromReview;
      this.quizOpen = true;
    },
    selectOption(idx) {
      if (this.quizAnswered) return; // 判定后锁定
      this.selectedOption = idx;
    },
    submitQuiz() {
      if (this.quizAnswered || this.selectedOption === null || !this.activeQuiz) return;
      const q = this.activeQuiz;
      const correct = this.selectedOption === q.answer;
      this.quizIsCorrect = correct;
      this.quizAnswered = true;

      // 1) 更新 quizStats(本地正确率信号)
      const stats = store.get('progress.quizStats', { attempts: 0, correct: 0 });
      const nextStats = {
        attempts: stats.attempts + 1,
        correct: stats.correct + (correct ? 1 : 0),
      };
      store.set('progress.quizStats', nextStats);

      // 2) 近 5 题正确率窗口(用本地 events 里最近的 quiz_answer 估算,含本次)
      const recentRate = this.recentCorrectRate(correct);

      // 3) 难度微调(§4.3),写回 difficulty
      const diff = store.get('difficulty', { current: 'L1', consecutiveWrong: 0 });
      const { next, changed } = adjustDifficulty(diff, correct, recentRate);
      store.set('difficulty', next);
      this.diffChange = changed;

      // 4) 错题入复习池 / 复习答对则清除(F-03)
      this.updateReviewPool(q, correct);

      // 5) 本地埋点(不外发)
      store.track('quiz_answer', { quizId: q.id, correct, selected: this.selectedOption });
    },
    /** 近5题正确率:读 events 中最近4次 quiz_answer + 本次,做窗口估算 */
    recentCorrectRate(currentCorrect) {
      const events = store.get('events', []);
      const recent = events
        .filter((e) => e.type === 'quiz_answer')
        .slice(-4)
        .map((e) => (e.payload && e.payload.correct ? 1 : 0));
      recent.push(currentCorrect ? 1 : 0);
      const sum = recent.reduce((a, b) => a + b, 0);
      return sum / recent.length;
    },
    updateReviewPool(quiz, correct) {
      const review = store.get('review', []);
      const idx = review.findIndex((r) => r.quizId === quiz.id);
      if (!correct) {
        // 答错:入池(已存在则重新标记未清除)
        if (idx >= 0) {
          review[idx] = { ...review[idx], cleared: false, wrongAt: ymd(new Date()) };
        } else {
          review.push({
            quizId: quiz.id,
            cardId: quiz.cardId,
            wrongAt: ymd(new Date()),
            cleared: false,
          });
        }
        store.set('review', review);
      } else if (this.reviewMode && idx >= 0) {
        // 复习模式答对:标记已清除
        review[idx] = { ...review[idx], cleared: true };
        store.set('review', review);
      }
    },
    closeQuiz() {
      this.quizOpen = false;
      this.activeQuiz = null;
      this.selectedOption = null;
      this.quizAnswered = false;
      this.diffChange = null;
      if (this.route === 'me') this.refreshMe(); // 复习通关后刷新池
    },
    get diffChangeLabel() {
      if (this.diffChange === 'up') return '表现不错,给你加点难度 ↑';
      if (this.diffChange === 'down') return '别急,先巩固一下基础 ↓';
      return '';
    },
    /** 选项样式:未判定=选中高亮;判定后=正确绿/错误标红 */
    optionClass(idx) {
      if (!this.quizAnswered) {
        return this.selectedOption === idx
          ? 'border-brand bg-brand-tint text-brand-dark font-medium'
          : 'border-slate-200 bg-white text-slate-600';
      }
      const answer = this.activeQuiz.answer;
      if (idx === answer) return 'border-brand bg-brand-tint text-brand-dark font-medium';
      if (idx === this.selectedOption) return 'border-red-300 bg-red-50 text-red-500';
      return 'border-slate-200 bg-white text-slate-400';
    },
    optionBadgeClass(idx) {
      if (!this.quizAnswered) {
        return this.selectedOption === idx
          ? 'border-brand bg-brand text-white'
          : 'border-slate-300 text-slate-400';
      }
      const answer = this.activeQuiz.answer;
      if (idx === answer) return 'border-brand bg-brand text-white';
      if (idx === this.selectedOption) return 'border-red-400 bg-red-400 text-white';
      return 'border-slate-200 text-slate-300';
    },
    optionBadge(idx) {
      if (this.quizAnswered) {
        if (idx === this.activeQuiz.answer) return '✓';
        if (idx === this.selectedOption) return '✕';
      }
      return String.fromCharCode(65 + idx); // A/B/C
    },

    // ---- 输入区:F-08 一屏三问(任务2)----
    toggleInterest(key) {
      const set = new Set(this.onboarding.interests);
      set.has(key) ? set.delete(key) : set.add(key);
      this.onboarding.interests = [...set];
    },
    get canSubmitOnboarding() {
      return this.onboarding.identity && this.onboarding.level;
    },
    submitOnboarding() {
      const tags = mapOnboardingToTags(this.onboarding);
      store.update((root) => {
        root.user.tags = tags;
        root.user.onboardedAt = new Date().toISOString();
        root.user.skippedOnboarding = false;
        root.difficulty.current = tags.level; // 自陈档位作为初始难度
      });
      store.track('onboarding_done', { tags });
      this.tags = tags;
      this.go('home');
      this.refreshTodayCard();
    },
    skipOnboarding() {
      store.update((root) => {
        root.user.tags = DEFAULT_TAGS;
        root.user.skippedOnboarding = true;
        root.difficulty.current = 'L1';
      });
      this.tags = DEFAULT_TAGS;
      this.go('home');
      this.refreshTodayCard();
    },

    // 供"我的"页重置(开发便利)
    resetAll() {
      store.reset();
      location.hash = '#/onboarding';
      location.reload();
    },
  };
}

window.finrookieApp = app;
