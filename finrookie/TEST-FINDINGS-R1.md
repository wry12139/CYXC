# 财小白 测试问题记录 (Round 1)

> 测试日期:2026-07-30
> 测试方式:逻辑层 node 断言(可执行)+ 全量静态代码追踪。**无浏览器自动化,G 类移动端视觉与部分交互需真机手工复核。**
> 状态说明:🔴 应修 / 🟡 建议修 / 🔵 待真机确认 / ✅ 已验证通过(不列问题,仅附通过项汇总)
> **修复状态(2026-07-30 更新):5 个代码层问题已全部修复,回归测试通过。详见文末「修复记录」。**

---

## 〇、问题 ↔ 修复一览

| 编号 | 级别 | 问题 | 修复要点 | 涉及文件 | 回归 |
|---|---|---|---|---|---|
| P1-01 | 🔴 | 离线首次打开无内容(SW 未预缓存 data/) | APP_SHELL 补入 3 个种子 JSON 预缓存;CACHE_VERSION v2→v3 | sw.js | ✅ |
| P2-01 | 🟡 | 难度标签四处文案不一致 | logic.js 抽 `LEVEL_LABELS` 单一来源,index.html 四处 inline 映射全替换 | logic.js / app.js / index.html | ✅ |
| P2-02 | 🟡 | viewport 禁用缩放(无障碍) | 去 `user-scalable=no`,加 `viewport-fit=cover` | index.html | ✅ + 🔵 手感 |
| P2-03 | 🟡 | 底部导航/浮层未适配 iOS 安全区 | 新增 `.pb-safe-nav`/`.pb-safe-sheet`,应用到导航+两浮层 | index.html | ✅ + 🔵 遮挡 |
| P2-04 | 🟡 | 脚本加载顺序竞态 | 改 `Alpine.data`+`alpine:init` 注册,`x-data` 去括号 | app.js / index.html | ✅ + 🔵 挂载 |

> 🔵 = 该项含运行时/视觉部分,node 环境无法端到端验,需真机复核。每条的现象/原因/修复/回归详见「五、修复记录」。

---

## 一、已发现问题(按严重度)

### 🔴 P1-01 离线首次打开无内容(SW 未预缓存 data/)
- **对应用例**:#17 离线可用
- **现象**:`sw.js` 的 `APP_SHELL` 只预缓存 HTML/JS/图标/CDN,**不含 `data/` 下任何内容 JSON**(knowledge-cards/quiz/glossary/briefings)。内容走 network-first + 失败回退缓存,但回退缓存只有在**联网成功访问过一次后**才存在。
- **影响**:用户「添加到主屏」后,若**首次打开就断网**,拿到的是空壳——出卡区会走内容加载失败态。PWA「离线可用」承诺打折。
- **证据**:sw.js:8-20 APP_SHELL 清单;sw.js fetch 分支 data/ 用 network-first。
- **修法方向**(留待修复):把种子 JSON 加入 APP_SHELL 预缓存,或首次加载后主动 warm 一遍内容缓存。

### 🟡 P2-01 难度标签三处文案不一致
- **对应用例**:#10 极端数值(观察时发现)
- **现象**:同一 L1/L2/L3 难度,三处显示不同中文:
  - 顶部 header(index.html:101):`L1=萌新 / L2=入门 / L3=进阶`
  - 卡片难度徽章(index.html:141):`L1=入门 / L2=进阶 / L3=高阶`
  - 建议引擎 levelName(logic.js:228):`L1=萌新 / L2=入门 / L3=进阶`
- **影响**:用户在卡片上看到「入门」,在报告建议里同一档却被称作「萌新」,概念混乱。
- **证据**:三处映射表字面不同。
- **修法方向**:统一为一套档位名(建议抽成 logic.js 单一导出常量,UI 复用)。

### 🟡 P2-02 viewport 禁用缩放(无障碍)
- **对应用例**:#18/#20 移动端显示
- **现象**:`<meta name="viewport" ... maximum-scale=1.0, user-scalable=no>`(index.html:5)禁止用户双指放大。
- **影响**:低视力用户无法放大页面,违反 WCAG 无障碍;iOS Safari 会忽略此限制,但 Android 生效。
- **证据**:index.html:5。
- **修法方向**:移除 `maximum-scale=1.0, user-scalable=no`。

### 🟡 P2-03 底部导航 / 浮层未适配 iOS 安全区
- **对应用例**:#20 安全区
- **现象**:底部 Tab(index.html:328 `fixed bottom-0`)、测验浮层 `pb-8`(:341)、术语弹层 `pb-8`(:389)均用固定 padding,未用 `env(safe-area-inset-bottom)`;`<head>` viewport 也无 `viewport-fit=cover`。
- **影响**:全面屏 iPhone(有 Home 指示条)上,底部导航按钮/浮层完成按钮可能被指示条压住,点击热区变小。
- **证据**:index.html:5 无 viewport-fit;:328/:341/:389 固定 padding。
- **修法方向**:viewport 加 `viewport-fit=cover`,底部元素加 `pb-[env(safe-area-inset-bottom)]` 或 `safe` 工具类。
- **备注**:🔵 具体遮挡程度需真机确认。

### 🟡 P2-04 脚本加载顺序隐患(app.js 早于 Alpine)
- **对应用例**:#1 正常流程(潜在偶发)
- **现象**:index.html 底部 app.js 用 `<script type="module">`(:400,defer 语义),Alpine 用 `<script defer>`(:401)。module 默认 defer,两者都等 DOM 解析完执行,顺序通常 app.js 先。`window.finrookieApp = app`(app.js:560)在 Alpine 初始化前挂载,当前能工作。
- **影响**:依赖执行时序,CDN 慢时理论上存在 Alpine 先于 `finrookieApp` 定义的竞态(会报 `finrookieApp is not defined`)。当前未复现,列为隐患。
- **证据**:index.html:400-401。
- **修法方向**:用 `alpine:init` 事件注册组件,或确保 Alpine 在 app.js 之后加载。
- **备注**:🔵 需弱网真机复现确认。

---

## 二、需真机手工确认(🔵 未能自动验证)

| 用例 | 关注点 | 说明 |
|---|---|---|
| #2 建议可点击闭环 | 「去复习」滚动定位、「去学 XX」出卡不被覆盖 | 竞态已修(57bda49)且逻辑仿真通过,但真机点击 + 平滑滚动效果需目视 |
| #15 内容加载超时 | 2s 超时 → 错误占位 + 重试恢复 | 需 DevTools 限速/断网手工触发 |
| #18 窄屏适配 | 375px 无横向滚动、导航不遮内容 | 纯视觉 |
| #19 弹层/浮层小屏 | 居中不溢出、长解析可滚、关闭可点 | 纯视觉 + 交互 |
| #23 SW 更新 | 强刷拿新内容、旧缓存被清 | 需改内容+bump 版本后对比 |

---

## 三、已验证通过项(逻辑层可执行断言,全绿)

| 用例 | 结论 |
|---|---|
| #3 自陈未选必填 | ✅ 提交按钮 `:disabled="!canSubmitOnboarding"` 受控 |
| #4 零数据看报告 | ✅ 冷启动 return + `masteryAnsweredTopics` 过滤,无 NaN/空条 |
| #5 未选兴趣提交 | ✅ 兜底 `['basics']`;空对象也不崩 |
| #6 localStorage 篡改 | ✅ 乱码/null/schemaVersion 不符 均回落默认,合法数据正常读 |
| #7 非法难度 L9 | ✅ `levelIndex` 兜底为 0,按 L1 处理不崩 |
| #8 术语无词条 | ✅ `openTerm` fallback「暂无解释」(代码路径确认) |
| #9 刷完全部卡 / 空卡库 | ✅ 分别 review_mode / empty 兜底,不空屏不报错 |
| #10 全对/全错 | ✅ 100% / 0% 正确率计算正确 |
| #11 超长打卡 999→1000 | ✅ 正常 +1 |
| #12 同日重复打卡 | ✅ 幂等,streak 不变;断签正确重置为 1 |
| 边界:最低档连错 | ✅ L1 不再降档 |

---

## 四、测试覆盖度小结

- 8 类维度全部触及。
- **逻辑/数据层**:可执行断言充分,结论可靠。
- **视图/交互/移动端**:受工具限制,以静态审查为主,5 条待真机复核。
- **本轮产出**:1 个 🔴、4 个 🟡、5 条 🔵 待确认。

---

## 五、修复记录(2026-07-30)

> 修复方式:node 语法检查 + 逻辑断言回归 + 静态落地复核。全部回归通过。CACHE_VERSION v2→v3。

### ✅ P1-01 离线首次打开无内容
- **现象**:PWA 添加到主屏后,若首次打开就断网,内容区走加载失败态,只剩空壳。
- **原因**:`sw.js` 的 `APP_SHELL` 只预缓存 HTML/JS/图标/CDN,不含 `data/` 内容 JSON;内容走 network-first,回退缓存要联网成功一次后才存在。
- **修复**:把 `knowledge-cards.json / quiz.json / glossary.json` 三个核心种子加入 `APP_SHELL` 预缓存(sw.js:18-21),安装时即缓存;bump `CACHE_VERSION` 到 v3 触发旧缓存清理。早报(briefings)仍走 network-first —— 早报页本就有空态兜底,且日更内容不宜永久钉进壳缓存。
- **回归**:✅ 断言 APP_SHELL 含三个 data 文件且文件真实存在;CACHE_VERSION=v3 确认。fetch 分支 network-first 的 `.catch(caches.match)` 现能命中预缓存。

### ✅ P2-01 难度标签三处文案不一致
- **现象**:同一 L1/L2/L3,顶部 header=萌新/入门/进阶、卡片徽章=入门/进阶/高阶、报告建议=萌新/入门/进阶,三套并存。
- **原因**:三处(实为四处,含收藏卡)各自写死 inline 映射对象,无单一来源。
- **修复**:logic.js 新增导出 `LEVEL_LABELS = {L1:'萌新',L2:'入门',L3:'进阶'}` 作全站唯一来源;`generateInsights` 的 levelName 改用它(logic.js);app.js 导入并挂到组件状态 `levelLabels`;index.html 四处 inline 映射(header:100 / 卡片徽章:141 / 我的页档位:224 / 收藏卡:296)全部替换为 `levelLabels[...]`。
- **回归**:✅ 残留 inline 映射 grep=0;`levelLabels` 引用=4;generateInsights 输出「L2→入门」正确;全对正确率仍 100% 不受影响。

### ✅ P2-02 viewport 禁用缩放
- **现象**:`user-scalable=no, maximum-scale=1.0` 禁止双指放大,低视力用户受阻(WCAG 无障碍)。
- **原因**:viewport meta 沿用了移动端「防误触缩放」的老写法。
- **修复**:index.html:5 改为 `width=device-width, initial-scale=1.0, viewport-fit=cover`,去掉缩放限制,同时启用安全区。
- **回归**:✅ grep 确认新 viewport 生效。实际缩放体验建议真机再感受一次(🔵)。

### ✅ P2-03 底部导航/浮层未适配 iOS 安全区
- **现象**:全面屏 iPhone 上底部 Tab、浮层完成按钮可能被 Home 指示条压住。
- **原因**:底部固定元素用固定 padding,无 `env(safe-area-inset-bottom)`;viewport 也无 `viewport-fit=cover`。
- **修复**:配合 P2-02 的 `viewport-fit=cover`;`<style>` 新增 `.pb-safe-nav`(纯安全区)和 `.pb-safe-sheet`(2rem + 安全区);应用到底部导航(:331)、测验浮层(:344)、术语弹层(:392)。
- **回归**:✅ grep 确认 2 处类定义 + 3 处应用落地。真机遮挡程度需目视复核(🔵)。

### ✅ P2-04 脚本加载顺序隐患
- **现象**:弱网下理论存在 Alpine 先于 `finrookieApp` 定义的竞态,会报 `finrookieApp is not defined`。
- **原因**:`x-data="finrookieApp()"` 依赖全局函数在 Alpine 初始化前挂载,时序脆弱。
- **修复**:app.js 改用 `Alpine.data('finrookieApp', app)` 注册,包在 `alpine:init` 事件里(若 Alpine 已就绪则直接注册),保留旧全局引用兼容;index.html `x-data` 改为无括号形式 `finrookieApp`。
- **回归**:✅ 语法检查通过;`x-data="finrookieApp"` 确认。运行时行为(Alpine 正常挂载)需真机/浏览器确认(🔵),因 node 环境无 Alpine 无法端到端验。

---

### 修复后回归汇总
| 项 | 结果 |
|---|---|
| node 语法检查(app/logic/sw) | ✅ 3/3 通过 |
| 逻辑断言回归(标签统一 + 核心逻辑) | ✅ 通过 |
| SW 清单 vs 实际文件 | ✅ 全部存在,v3 |
| HTML 修复静态落地复核 | ✅ 4 项全落实,无残留 |
| 待真机复核 | 🔵 P2-02 缩放手感、P2-03 遮挡、P2-04 运行时挂载 + 原 5 条视觉项 |
