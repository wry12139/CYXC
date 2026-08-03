import { store } from './store.js';
import { repository } from './repository.js';
import * as authApi from './auth.js';
import { pullAndMerge } from './sync.js';
import { askAI as askAIApi } from './ai.js';
import {
  mapOnboardingToTags,
  DEFAULT_TAGS,
  pickTodayCard,
  adjustDifficulty,
  checkIn,
  ymd,
  analyzeMastery,
  generateInsights,
  LEVEL_LABELS,
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
    articles: [],           // 延伸阅读文章库(按主题关联到当前知识卡)
    expandedArticleIds: [], // 已展开正文的文章 id 列表(可同时展开多篇,互不影响)
    // 首页结果区
    todayCard: null,
    cardReason: '',
    // 术语搜索(首页替换今日一课卡片区)
    searchQuery: '',          // 输入框内容
    searchMode: false,        // 是否处于搜索结果态(替换每日卡)
    searchResults: [],        // 命中的术语名列表(最佳匹配在前)
    activeSearchTerm: null,   // 当前展示的术语名
    activeSearchText: '',     // 当前术语解释
    // AI 兜底(本地词库未命中时,已登录可问 AI)
    aiAnswer: null,
    aiAsking: false,
    aiError: null,
    aiCached: false,
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
    briefingDates: [],       // 近期可用早报日期列表(往期浏览,新→旧)
    activeBriefingDate: null,// 当前查看的日期
    // onboarding 输入区(F-08)
    onboarding: { identity: '', level: '', interests: [] },
    // 用户态镜像(展示用)
    tags: DEFAULT_TAGS,
    streak: 0,
    levelLabels: LEVEL_LABELS, // 难度档位中文名(全站唯一来源,修复 P2-01)

    // ---- 生命周期 ----
    async init() {
      this.tags = store.get('user.tags', DEFAULT_TAGS);
      this.streak = store.get('progress.streak', 0);
      // 恢复登录态显示(同步);云端拉取合并放到内容加载之后,避免抢在 loadContent 前调 refreshMe
      this.authUser = authApi.getUsername();

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

      // 内容加载完成后再拉取合并云端数据(此时 cards/quiz 已就绪,refreshMe 不会因空数据出错)
      if (authApi.isLoggedIn()) {
        pullAndMerge().then(() => {
          this.tags = store.get('user.tags', DEFAULT_TAGS);
          this.streak = store.get('progress.streak', 0);
          if (this.route === 'me') this.refreshMe();
          if (this.route === 'home') this.refreshTodayCard();
        }).catch(() => {});
      }
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
      // 延伸阅读为增强内容,单独加载:失败只是不展示,绝不影响核心知识卡
      try {
        const articles = await repository.getArticles();
        this.articles = Array.isArray(articles) ? articles : [];
      } catch (e) {
        console.warn('[articles] load failed, skip extended reading:', e.message);
        this.articles = [];
      }
    },

    async retryContent() {
      this.loading = true;
      await this.loadContent();
      if (!this.contentError && this.route === 'home') await this.refreshTodayCard();
      this.loading = false;
    },

    // ---- 早报加载:发现近期可用期次 + 默认展示最近一期(F-04, §6)----
    async loadBriefing() {
      this.briefingLoading = true;
      this.briefingError = null;
      this.briefingFallback = false;
      // 从今日往前回溯 7 天,收集所有真实存在的早报日期(新→旧)
      const base = new Date();
      const dates = [];
      let timedOut = false;
      for (let i = 0; i < 7; i++) {
        const d = new Date(base);
        d.setDate(base.getDate() - i);
        const dateStr = ymd(d);
        try {
          const data = await repository.getBriefing(dateStr);
          if (data && Array.isArray(data.items)) dates.push(dateStr);
        } catch (e) {
          // 该日无早报(404)继续;超时视为网络问题,停止探测
          if (e.code === 'TIMEOUT') { timedOut = true; break; }
        }
      }
      this.briefingDates = dates;
      if (dates.length === 0) {
        this.briefingError = { code: timedOut ? 'TIMEOUT' : 'NO_BRIEFING' };
        this.briefingLoading = false;
        return;
      }
      // 默认展示最近一期(列表首个);非今日则标记回退提示
      await this.showBriefing(dates[0]);
    },

    /** 加载并展示指定日期的早报(供日期切换调用) */
    async showBriefing(dateStr) {
      if (!dateStr) return;
      this.briefingLoading = true;
      this.briefingError = null;
      try {
        const data = await repository.getBriefing(dateStr);
        if (data && Array.isArray(data.items)) {
          this.briefing = data;
          this.activeBriefingDate = dateStr;
          // 回退提示仅用于「今日尚无早报」的被动场景;用户主动翻往期不提示
          const todayStr = ymd(new Date());
          this.briefingFallback = dateStr !== todayStr && !this.briefingDates.includes(todayStr);
          store.track('briefing_open', { date: dateStr, fallback: this.briefingFallback });
        } else {
          this.briefingError = { code: 'NO_BRIEFING' };
        }
      } catch (e) {
        this.briefingError = { code: e.code === 'TIMEOUT' ? 'TIMEOUT' : 'NO_BRIEFING' };
      } finally {
        this.briefingLoading = false;
      }
    },

    /** 日期 chip 显示文案:今天/昨天/MM-DD */
    briefingDateLabel(dateStr) {
      const today = ymd(new Date());
      const y = new Date();
      y.setDate(y.getDate() - 1);
      if (dateStr === today) return '今天';
      if (dateStr === ymd(y)) return '昨天';
      return dateStr.slice(5); // MM-DD
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
      this.expandedArticleIds = []; // 换卡后收起上一张卡展开的延伸阅读
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

    /** 延伸阅读:与当前知识卡主题相关的文章(主题有交集即匹配,最多 3 篇)*/
    get relatedArticles() {
      const card = this.todayCard;
      if (!card || !Array.isArray(this.articles) || !this.articles.length) return [];
      const topics = Array.isArray(card.topics) ? card.topics : [];
      if (!topics.length) return [];
      const matched = this.articles.filter(
        (a) => Array.isArray(a.topics) && a.topics.some((t) => topics.includes(t))
      );
      return matched.slice(0, 3);
    },
    /** 站内展开/收起某篇文章正文(独立开合,互不影响)*/
    toggleArticle(id) {
      if (this.expandedArticleIds.includes(id)) {
        this.expandedArticleIds = this.expandedArticleIds.filter((x) => x !== id);
      } else {
        this.expandedArticleIds = [...this.expandedArticleIds, id];
        store.track('article_expand', { id });
      }
    },
    /** 某篇文章是否处于展开态 */
    isArticleExpanded(id) {
      return this.expandedArticleIds.includes(id);
    },

    /** 招牌:根据连续打卡天数给一句成长鼓励(与 growEmoji 三档对齐)*/
    get streakMessage() {
      const s = this.streak;
      if (s <= 0) return '种下第一颗种子';
      if (s < 7) return '刚冒芽,每天来浇浇水';
      if (s < 30) return '长势喜人,别停下';
      return '已经枝繁叶茂啦';
    },
    /** 招牌图标:与 streakMessage 同阈值(芽/叶/树)*/
    get growEmoji() {
      const s = this.streak;
      if (s < 7) return '🌱';
      if (s < 30) return '🌿';
      return '🌳';
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

    // ---- 术语搜索:替换今日一课卡片区展示查得的术语解释 ----
    /** 搜索:先匹配术语名(命中优先),再匹配解释正文;结果去重、术语名命中排前 */
    async search() {
      const q = (this.searchQuery || '').trim().toLowerCase();
      if (!q) return;
      const terms = Object.keys(this.glossary);
      const byName = terms.filter((t) => t.toLowerCase().includes(q));
      const byText = terms.filter(
        (t) => !byName.includes(t) && String(this.glossary[t]).toLowerCase().includes(q)
      );
      this.searchResults = [...byName, ...byText];
      this.searchMode = true;
      store.track('term_search', { query: q, hits: this.searchResults.length });
      if (this.searchResults.length) {
        this.selectSearchResult(this.searchResults[0]);
      } else {
        this.activeSearchTerm = null;
        this.activeSearchText = '';
        this.resetAI();
        // 本地词库未命中且已登录:自动调 AI 兜底(回车触发,每次搜索最多一次调用)
        if (this.isAuthed) await this.askAI();
      }
    },
    /** 切换展示某个命中的术语 */
    selectSearchResult(term) {
      this.activeSearchTerm = term;
      this.activeSearchText = this.glossary[term] || '暂无解释';
      this.resetAI();
    },
    /** 退出搜索态,恢复今日一课 */
    exitSearch() {
      this.searchMode = false;
      this.searchQuery = '';
      this.searchResults = [];
      this.activeSearchTerm = null;
      this.activeSearchText = '';
      this.resetAI();
    },

    // ---- AI 名词科普兜底 ----
    resetAI() {
      this.aiAnswer = null;
      this.aiError = null;
      this.aiAsking = false;
      this.aiCached = false;
    },
    async askAI() {
      const q = (this.searchQuery || '').trim();
      if (!this.isAuthed || !q || this.aiAsking) return;
      this.aiAnswer = null;
      this.aiError = null;
      this.aiAsking = true;
      try {
        const r = await askAIApi(q, authApi.getToken());
        this.aiAnswer = r.answer;
        this.aiCached = !!r.cached;
        store.track('ai_ask', { cached: !!r.cached });
      } catch (e) {
        this.aiError = (e.code === 'TIMEOUT')
          ? '网络不太顺,待会再试试~'
          : '暂时问不了,待会再试试~';
      } finally {
        this.aiAsking = false;
      }
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
    // 术语收藏(存 favorites.terms,store 已预留该字段)
    isTermFav(term) {
      return store.get('favorites.terms', []).includes(term);
    },
    toggleTermFav(term) {
      if (!term) return;
      const favs = store.get('favorites.terms', []);
      const next = favs.includes(term)
        ? favs.filter((t) => t !== term)
        : [...favs, term];
      store.set('favorites.terms', next);
      this.refreshMe();
    },

    // ---- F-03 我的页:收藏列表 + 复习池 ----
    favCards: [],        // 已收藏的知识卡对象列表(派生)
    favTerms: [],        // 已收藏的术语名列表(派生,过滤失效)
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
      // 收藏术语:保序 + 过滤 glossary 里已不存在的
      const favTermNames = store.get('favorites.terms', []);
      this.favTerms = favTermNames.filter((t) => t in this.glossary);
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
      if (r === null || r === undefined) return 'text-ink-faint';
      return r >= 0.8 ? 'text-brand' : r >= 0.5 ? 'text-amber' : 'text-clay';
    },
    get masteryBarColor() {
      const r = this.mastery ? this.mastery.overallRate : null;
      if (r === null || r === undefined) return 'bg-paper-line';
      return r >= 0.8 ? 'bg-brand' : r >= 0.5 ? 'bg-amber' : 'bg-clay';
    },
    insightBoxClass(type) {
      return {
        praise: 'bg-brand-tint text-brand-dark',
        suggest: 'bg-amber/10 text-amber-dark',
        warn: 'bg-clay-tint text-clay-dark',
        guide: 'bg-paper text-ink-soft',
      }[type] || 'bg-paper text-ink-soft';
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
          ? 'border-brand bg-brand-tint text-brand-dark font-bold'
          : 'border-paper-line bg-paper-card text-ink-soft';
      }
      const answer = this.activeQuiz.answer;
      if (idx === answer) return 'border-brand bg-brand-tint text-brand-dark font-bold';
      if (idx === this.selectedOption) return 'border-clay/40 bg-clay-tint text-clay';
      return 'border-paper-line bg-paper-card text-ink-faint';
    },
    optionBadgeClass(idx) {
      if (!this.quizAnswered) {
        return this.selectedOption === idx
          ? 'border-brand bg-brand text-white'
          : 'border-paper-line text-ink-faint';
      }
      const answer = this.activeQuiz.answer;
      if (idx === answer) return 'border-brand bg-brand text-white';
      if (idx === this.selectedOption) return 'border-clay bg-clay text-white';
      return 'border-paper-line text-ink-faint';
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

    // ---- 账号/登录(阶段二)----
    authUser: null,
    authOpen: false,
    authMode: 'login',
    authForm: { username: '', password: '' },
    authError: '',
    authBusy: false,

    get isAuthed() { return !!this.authUser; },
    openAuth(mode) { this.authMode = mode || 'login'; this.authError = ''; this.authForm = { username: '', password: '' }; this.authOpen = true; },
    closeAuth() { this.authOpen = false; this.authError = ''; },
    switchAuthMode() { this.authMode = this.authMode === 'login' ? 'register' : 'login'; this.authError = ''; },

    async doLogin() {
      if (this.authBusy) return;
      this.authBusy = true; this.authError = '';
      const r = await authApi.login(this.authForm.username.trim(), this.authForm.password);
      this.authBusy = false;
      if (r.error) { this.authError = r.error === 'bad_credentials' ? '用户名或密码错误' : '登录失败,请稍后再试'; return; }
      this.authUser = r.username;
      this.authOpen = false;
      await pullAndMerge();
      this.tags = store.get('user.tags', DEFAULT_TAGS);
      this.streak = store.get('progress.streak', 0);
      if (this.route === 'me') this.refreshMe();
    },
    async doRegister() {
      if (this.authBusy) return;
      this.authBusy = true; this.authError = '';
      const u = this.authForm.username.trim();
      const r = await authApi.register(u, this.authForm.password);
      if (r.error) {
        this.authBusy = false;
        this.authError = r.error === 'username_taken' ? '该用户名已被使用' : '注册失败(用户名和密码不能为空)';
        return;
      }
      const lr = await authApi.login(u, this.authForm.password);
      this.authBusy = false;
      if (lr.error) { this.authMode = 'login'; this.authError = '注册成功,请登录'; return; }
      this.authUser = lr.username;
      this.authOpen = false;
      await pullAndMerge();
      this.tags = store.get('user.tags', DEFAULT_TAGS);
      this.streak = store.get('progress.streak', 0);
      if (this.route === 'me') this.refreshMe();
    },
    async doLogout() {
      await authApi.logout();
      this.authUser = null;
    },

    // 供"我的"页重置(开发便利)
    resetAll() {
      store.reset();
      location.hash = '#/onboarding';
      location.reload();
    },
  };
}

// 组件注册:用 alpine:init 事件,避免依赖「app.js 早于 Alpine 执行」的脆弱时序(修复 P2-04)。
// 若 Alpine 已就绪(理论上 module 先于 defer 脚本,但不保证 CDN 时序),直接注册;否则等事件。
function registerComponent() {
  window.Alpine.data('finrookieApp', app);
}
if (window.Alpine) {
  registerComponent();
} else {
  document.addEventListener('alpine:init', registerComponent);
}
// 兼容旧全局引用(仍暴露,不影响)
window.finrookieApp = app;
