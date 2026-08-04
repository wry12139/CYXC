## Phase 1 Fixes 验证 - 前端交互测试

**本地服务：http://127.0.0.1:8080/**

### 快速检查清单

#### 1️⃣ 打开应用
- 打开浏览器：http://127.0.0.1:8080/
- F12 打开开发者工具，切换到 Console 标签页
- 确认没有红色错误

#### 2️⃣ 验证 Fix 2: 稳定 ID（最直接）
- 首页显示"今日一课"
- 打开 Console，运行：
  ```javascript
  console.log(app.todayCard.id)
  ```
- 然后查看 `data/knowledge-cards.json` 中是否有同样的 ID
- **预期**：Console 输出的 ID 与 JSON 中某张卡的 ID 完全一致

#### 3️⃣ 验证 Fix 3: 迁移成功（数据加载）
- 首页应该能正常显示知识卡、可以点"测一测"
- Console 运行：
  ```javascript
  console.log(app.allCards.length, app.allQuizzes.length, app.glossary.size)
  ```
- **预期**：输出类似 `20 20 101` 之类的数字（20+ 张卡、20+ 题、100+ 术语）

#### 4️⃣ 验证 Fix 4: Admin 密码（查日志）
- 打开终端，运行：
  ```bash
  ps aux | grep "python3 -m http.server" | grep -v grep
  ```
- 看到进程还在运行就说明服务正常
- 后端日志（服务器）应该显示：
  ```
  [WARNING] Admin account 'admin' created with temporary password.
  ```

### 有问题时的诊断

**症状：知识卡显示不出来 / ID 不对**
→ 检查 Console 是否有错误，运行 `console.log(app.allCards)` 看数据是否加载

**症状：点击"测一测"出现题目错误**
→ Console 运行 `app.todayCard` 检查卡片对象，确认 `quizIds` 是否在 `allQuizzes` 中能找到

**症状：登录后数据混乱**
→ F12 → Application → Clear site data + Unregister Service Workers，硬刷新（Ctrl+Shift+R）

### 完成后告诉我
- [X] 应用能正常打开
- [ ] 知识卡 ID 与 JSON 一致
- [ ] 数据加载正常（20+ 卡、20+ 题、100+ 术语）
- [ ] 没有红色错误
- [ ] 后端日志有 WARNING 信息（或已设置 ADMIN_PASSWORD）
