# 财小白 (FinRookie) 手动测试清单 v1

> **测试环境**:`python -m http.server 8080 --bind 0.0.0.0`,手机/浏览器访问 `http://<本机IP>:8080/`
> **前置**:首测前先清 localStorage(DevTools → Application → Clear storage)以模拟新用户
> **勾选**:测过一条在 `[ ]` 内打 `x`

覆盖维度:正常流程 / 空输入 / 非法输入 / 极端数值 / 重复操作 / 网络·工具失败 / 移动端显示 / 刷新页面。共 23 条。

---

## A. 正常流程

- [ ] **1. 完整主线闭环**
  - 步骤:新用户 → 自陈三问(身份/水平/兴趣)→ 提交 → 首页出卡 → 点「测一测」→ 答题 → 看解析 → 进「我的」
  - 预期:全程无报错;学习报告出现总体正确率 + 分主题条 + 建议卡;打卡天数 = 1
  - 依据:app.js `submitOnboarding` → `refreshTodayCard` → `submitQuiz` → `refreshMe`

- [ ] **2. 建议可点击闭环 🔴**
  - 步骤:故意答错 ≥1 题 → 进「我的」→ 点建议里「去复习 →」/「去学「XX」→」
  - 预期:「去复习」跳「我的」并滚动到复习池;「去学 XX」跳首页且出该主题卡(**不被随机卡覆盖**)
  - 依据:app.js `handleInsightAction` / `learnTopic`(已修竞态 commit 57bda49)

## B. 空输入

- [ ] **3. 自陈未选必填项**
  - 步骤:自陈页只选兴趣、不选身份或水平 → 看「开始」按钮
  - 预期:提交按钮置灰/不可点
  - 依据:app.js `canSubmitOnboarding`(要求 identity + level)

- [ ] **4. 零数据看报告**
  - 步骤:全新用户跳过自陈 → 直接进「我的」(一题没答)
  - 预期:报告显示冷启动引导语 + 「去学习 →」按钮;**不显示 NaN%、不显示空主题条**
  - 依据:logic.js 冷启动 return;`masteryAnsweredTopics` 过滤 attempts>0

- [ ] **5. 未选兴趣提交**
  - 步骤:自陈选身份+水平,兴趣一个不选 → 提交
  - 预期:不崩;兴趣兜底为 `['basics']`
  - 依据:logic.js `mapOnboardingToTags`

## C. 非法输入

- [ ] **6. localStorage 被篡改 🔴**
  - 步骤:DevTools 把 `finrookie:v1` 的值改成 `{乱码` 或 `null` → 刷新
  - 预期:应用不白屏,回落默认状态正常启动
  - 依据:store.js `readRoot` try/catch + schemaVersion 校验

- [ ] **7. 手改非法难度值 🔴**
  - 步骤:把 `difficulty.current` 改成 `"L9"` → 答题触发难度调整
  - 预期:不崩;按 L1 处理
  - 依据:logic.js `levelIndex` = `Math.max(0, indexOf)`

- [ ] **8. 术语点击无对应词条**
  - 步骤:(需构造)点一个 glossary 里没有的 `data-term`
  - 预期:弹层显示「暂无解释」,不显示 undefined
  - 依据:app.js `openTerm` fallback

## D. 极端数值

- [ ] **9. 刷完全部 20 卡**
  - 步骤:连续点「下一张」直到无新卡
  - 预期:进入 review_mode 兜底,**不空屏、不报错**
  - 依据:logic.js `pickTodayCard` 第 4 级降级

- [ ] **10. 全对 / 全错**
  - 步骤:20 题全答对(或全答错)→ 看报告
  - 预期:正确率显示 100%(或 0%);进度条宽度正确;建议措辞匹配(表扬 / 别气馁)
  - 依据:logic.js 分档;index.html 进度条宽度

- [ ] **11. 超长连续打卡**
  - 步骤:手改 `progress.streak=999`、`lastCheckIn` 为昨天 → 学一张卡
  - 预期:打卡数 +1 = 1000,UI 不溢出错位
  - 依据:logic.js `checkIn`

## E. 重复操作

- [ ] **12. 同日重复打卡**
  - 步骤:同一天多次学卡/答题
  - 预期:streak 只 +1,不重复累加(幂等)
  - 依据:logic.js `lastCheckIn === today` 提前 return

- [ ] **13. 快速反复收藏/取消**
  - 步骤:对同一张卡狂点收藏按钮 5 次
  - 预期:状态最终一致,收藏列表无重复 id
  - 依据:app.js `toggleFav`(filter/includes)

- [ ] **14. 复习题重复重做**
  - 步骤:同一错题重做通关 → 再进复习池找它
  - 预期:通关后标 cleared、移出复习池,不残留
  - 依据:app.js `updateReviewPool`

## F. 网络 / 工具失败

- [ ] **15. 内容加载超时 🔴**
  - 步骤:DevTools Network 设 Slow 3G / 断网 → 首次进首页
  - 预期:2s 超时后显示错误占位 + 重试按钮;点重试可恢复
  - 依据:repository.js `TIMEOUT_MS=2000`;app.js `retryContent`

- [ ] **16. 今日早报缺失**
  - 步骤:进「早报」页(今日无 JSON)
  - 预期:回退最近一期并提示「今日生成中」;7 天内都无则空态「最近还没有早报」
  - 依据:app.js `loadBriefing` 回溯 7 天

- [ ] **17. 离线可用 (PWA)**
  - 步骤:首次联网加载后 → 断网 → 重开应用
  - 预期:壳与已缓存内容仍可用
  - 依据:sw.js(CACHE_VERSION v2)

## G. 移动端显示

- [ ] **18. 窄屏适配**
  - 步骤:375px(iPhone SE)宽度查看各页
  - 预期:无横向滚动条;底部导航栏不遮内容;卡片 padding 正常

- [ ] **19. 术语弹层 / 测验浮层**
  - 步骤:小屏点术语、点「测一测」
  - 预期:弹层/浮层居中不溢出;长解析可滚动;关闭按钮可点

- [ ] **20. 安全区 / 长文字**
  - 步骤:有刘海/圆角的机型;超长卡片标题
  - 预期:底部导航避开 Home 指示条;标题换行不截断

## H. 刷新页面

- [ ] **21. 状态持久化 🔴**
  - 步骤:答几题、收藏、打卡后 → F5 刷新
  - 预期:打卡数、收藏、复习池、难度档全部保留
  - 依据:store.js localStorage

- [ ] **22. 路由还原**
  - 步骤:在「我的」页(`#/me`)刷新
  - 预期:刷新后仍停在「我的」页,非跳回首页
  - 依据:app.js `currentRoute()` + hashchange

- [ ] **23. SW 更新**
  - 步骤:改内容 + bump CACHE_VERSION 后 → 普通刷新 vs 强刷
  - 预期:强刷(Ctrl+Shift+R)拿到新内容;旧缓存被清
  - 依据:sw.js 清非当前版本缓存

---

**优先必测(🔴)**:#2 竞态修复、#6/#7 非法输入容错、#15 超时降级、#21 持久化。
