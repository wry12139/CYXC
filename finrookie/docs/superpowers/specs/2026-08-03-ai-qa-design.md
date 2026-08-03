# 财小白 AI 问答(术语兜底型)设计文档

- 日期:2026-08-03
- 关联:阶段二待决策项 3(AI 问答)。前置地基见 `2026-07-31-user-account-backend-design.md`。
- 状态:设计已与用户逐节确认通过,待写实现计划。

## 1. 目标与定位

给财小白加一层 **AI 名词科普兜底**:当用户在术语搜索栏输入的词,本地 101 词 glossary 查不到时,提供"问问 AI"入口,调用金融科普 AI 返回白话解释。

**核心原则(与财小白一贯取向一致):**
- 本地优先:本地词库命中就完全不碰 AI(省钱 + 离线可用)。
- AI 是增强兜底:离线 / 未登录 / AI 挂掉时,它安静消失,核心学习体验零损伤。
- 合规红线:AI 只做概念科普,绝不推荐具体标的、不预测涨跌。
- 隐私铁律:用户之间彻底看不到彼此的提问。

## 2. 六项关键决策(用户已裁决)

| 决策项 | 选定 | 理由 |
|---|---|---|
| 入口形态 | 术语搜索兜底(轻) | 改动最小、省钱、离线仍可用 |
| 后端路径 | 新起独立 AI 服务(端口 8092) | 与 8091 用户后端进程隔离,崩了不影响登录/同步 |
| 合规尺度 | 中:可谈策略概念,不荐股不预测 | 回答直接给小白看,系统 prompt 硬约束 + 出口过滤 |
| 成本控制 | 加服务端问答缓存 | 相同问题不重复烧钱 |
| 登录门槛 | 必须登录 | 防匿名刷接口,成本可控 |
| 缓存隔离 | 匿名共享缓存(不含 user_id) | 隐私与省钱兼得:不记录身份,自然无从泄露 |

## 3. 整体架构与数据流

```
用户在首页术语搜索栏输入
   │
   ▼
本地 glossary.json(101 词)先匹配
   │
   ├─ 命中 ──→ 照旧显示术语卡(完全不碰 AI)
   │
   └─ 未命中 ──→ 空态出现"🤖 问问 AI"按钮(仅已登录时)
                    │  点击
                    ▼
        前端 js/ai.js
           │  POST http://10.159.3.80:8092/api/ask
           │  body { question }  + Authorization: Bearer <token>
           ▼
        独立 AI 服务 backend/ai_server.py(端口 8092)
           │  1. 验 token —— 直接读同机 finrookie.db,复用 auth.lookup_session
           │  2. 查缓存 —— ai_cache 表命中则秒回,不调 AI
           │  3. 未命中 —— 读 ~/finrookie-secret/ai.env,调中转站 new-api.finstep.cn
           │  4. 出口合规过滤(复用 pipeline 违规词表)—— 违规返固定安全话术
           │  5. 写缓存 + 返回 { answer, cached }
           ▼
        前端渲染进搜索结果卡(复用知识卡视觉 + 免责声明)
```

**关键取舍:独立进程但共享 db 验 token。** 8092 是纯新增进程,与 8091 隔离(崩溃互不影响);但不重复造鉴权,直接只读打开同机 `finrookie.db` 复用 `auth.lookup_session`,也不绕 HTTP 回问 8091。

## 4. 后端组件(backend/,纯 Python 标准库,零 pip)

### 4.1 ai_server.py — 独立 HTTP 服务,端口 8092
- `POST /api/ask` — body `{question}`,须带 `Bearer token`。
  流程:验 token(失败 401)→ 校验 question 非空且 ≤200 字(失败 400)→ 入口合规检查 → 查缓存 → 未命中调 AI → 出口合规过滤 → 写缓存 → 返 `{answer, cached}`。
- `OPTIONS` — CORS 预检,复用现有 `_cors()` 那套头。
- 复用 `db.py` / `auth.py`,不修改它们。
- 每步 try/finally 关 db 连接(沿用 server.py 模式)。

### 4.2 ai_client.py — 调中转站的纯函数
- 读 `~/finrookie-secret/ai.env`(`FR_AI_KEY / FR_AI_BASE / FR_AI_MODEL`)。
- `urllib` POST 到 `{FR_AI_BASE}/v1/chat/completions`,Bearer 认证,`claude-haiku-4-5-20251001`。
- **TLS 必须验证**(不关 CERT_NONE —— pipeline 踩过的坑,AI 无审核直出给用户,须防中间人)。
- 超时 20s,失败抛异常由 server 兜成友好错误。
- 系统 prompt 固化"中等尺度"人设:面向零基础新手的金融科普助手,只做名词解释和概念科普,可讲策略概念但**绝不推荐具体标的、不预测涨跌**,回答简短白话(≤150 字)。

### 4.3 compliance.py — 违规词表 + 检查(与 pipeline 共享同一份词表)
- **入口**:拒答"帮我买/该不该买某只股"类提问。
- **出口**:AI 回答命中违规词(买入/卖出/预测/荐股/涨到/必涨/逢低布局等)则丢弃,返固定安全话术:"我只能帮你理解概念,不能给出具体买卖或涨跌建议哦~"。

### 4.4 ai_cache 表(新建在同一 finrookie.db,不含 user_id)
- 字段:`question_hash`(主键,sha256(归一化问题))、`question`、`answer`、`created_at`。
- 归一化 = 去空格 + 小写,让"什么是ETF"和"什么是 ETF"命中同一条。
- **不记录 user_id** —— 匿名金融百科字典,任何登录用户命中同一问题都秒回。
- `ai_server.py` 启动时 `CREATE TABLE IF NOT EXISTS`,不动现有 users/sessions/user_data 三表。

## 5. 隐私隔离(用户要求 + 财小白铁律)

- **无任何"列出提问"接口**:`/api/ask` 只吃单个问题、只吐单个答案。系统里不存在能查到"谁问过什么"的路径 —— 这是隔离的根本保证。
- **token 仅用于准入**:验证"你是合法登录用户"后即丢弃,不与问题/答案关联落库。
- **缓存表不含 user_id**:根本不记录身份,自然没有"别人问题"可泄露。
- 结果:用户之间彻底看不到彼此的提问;通用金融名词仍可共享缓存省钱。

## 6. 前端组件

### 6.1 新增 js/ai.js(纯函数模块)
- `askAI(question)` — 带当前 token POST 到 `http://10.159.3.80:8092/api/ask`,返 `{answer, cached}` 或抛错。复用 auth.js 的 token 管理 + repository.js 的超时/错误模式。

### 6.2 改 js/app.js
- 新状态:`aiAnswer / aiAsking / aiError`(`aiAnswer` 初始 null)。
- 新方法 `askAI()`:调 ai.js,置 loading → 成功填 `aiAnswer` → 失败填友好错误。
- 触发条件:`searchMode && searchResults.length === 0`(本地没命中)**且已登录** → 才渲染按钮。
- 埋点 `ai_ask`(本地不外发,延续合规红线)。

### 6.3 改 index.html
- 术语搜索空态区下方:
  - 已登录:"🤖 没找到?问问 AI"按钮 → loading → AI 回答卡(复用知识卡视觉,底部小字免责声明"AI 科普仅供学习,不构成投资建议")。
  - 未登录:提示"登录后可以问 AI 哦" + 复用现有登录入口。
- **裸读守卫**:AI 回答卡里所有 `aiAnswer.xxx` 都加 `aiAnswer &&` 守卫(x-show 内表达式仍会求值,`aiAnswer` 初始 null,踩过的崩溃坑)。

### 6.4 改 sw.js
- bump `CACHE_VERSION`(v12 → v13),`js/ai.js` 加进壳缓存。
- AI 接口本身 network-only(不缓存动态回答)。

## 7. 错误处理(前端逐档降级)

| 情况 | 表现 |
|---|---|
| 未登录 | 不显示 AI 按钮,提示"登录后可问" |
| 网络失败 / 超时(20s) | "网络不太顺,待会再试试~",本地搜索照常 |
| AI 服务挂 / 返错 | 同上友好话术,不暴露技术细节 |
| 回答被合规拦下 | 返固定安全话术(非报错) |

## 8. 部署与运维

- `scp` 增量传:后端 `ai_server.py / ai_client.py / compliance.py` + 前端 `js/ai.js / app.js / index.html / sw.js`。**绝不碰 data/**(服务器早报是 crontab 生成的,本机没有)。
- `ai_cache` 表:`ai_server.py` 启动时自建,不动现有三表。
- crontab 加第 4 条:`@reboot` 自启 8092(`cd ~/finrookie-app/backend && setsid python3 ai_server.py`)。
- 连通验证:本机 `curl http://10.159.3.80:8092/api/ask`(无 token 应返 401)。
- 回滚:8092 是纯新增进程,出问题直接 kill,不影响 8091/8090。

## 9. 测试

- 后端 `backend/tests/test_ai.py`(unittest,延续现有):
  - token 缺失/失效 → 401;空问题/超长 → 400。
  - 缓存命中不调 AI(mock ai_client)。
  - 合规过滤:入口拦截 + 出口拦截。
  - ai_cache 表无 user_id 字段(隐私回归)。
  - **AI 中转真实调用不进单测**(靠 mock),仅服务器手动 curl 冒烟一次。
- 前端 `ai.js`:node 断言(token 拼装、错误分支)。
- 端到端(输入未命中词 → 出按钮 → 点 → 出答案):**无浏览器自动化,需用户本机真机确认** —— 财小白一贯验证限制。

## 10. 非目标(本次不做)

- 独立聊天页 / 多轮对话 / 自由问答助手(阶段二后续可扩)。
- 调用限流(内网、用户少,先不过度设计)。
- 提问历史记录 / 收藏 AI 回答。
- 知识卡 / 题目的 AI 生成(pipeline 里另有 TODO)。
