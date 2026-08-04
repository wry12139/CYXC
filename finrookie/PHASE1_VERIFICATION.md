## Phase 1 Fixes 验证清单（手动浏览器测试）

服务器地址：**http://127.0.0.1:8080/**

### Fix 1: Soft Delete + 版本历史 ✅
**场景**：后端 CMS 删除内容后，前端应该看不到，但版本历史保留

**测试步骤**：
1. 打开浏览器开发者工具 (F12 → Network)
2. 登录后台管理（如果有 /admin 路由）
3. 创建一个测试内容 → 查看前端能否显示 → 删除 → 确认前端消失
4. 用 curl 查询版本历史：`curl http://127.0.0.1:8080/api/versions/<content_id>`
   - 应该返回 ≥2 条记录（create + delete）
   - 删除后的内容不在 /api/content 列表中，但版本保留

**预期结果**：❌ 删除后不可见 / 📜 版本历史完整

---

### Fix 2: 稳定 Seed ID ✅
**场景**：知识卡、题目、术语的 ID 来自 JSON，迁移后 ID 保持不变

**测试步骤**：
1. 查看 `data/knowledge-cards.json` 中第一张卡的 ID（如 `"id": "card-001"`）
2. 打开前端首页，进入"今日一课"
3. 点击知识卡 → 打开浏览器开发者工具 → 查看 HTML 中卡片的 data 属性或 JS 状态
4. 确认显示的卡片 ID 与 JSON 中的 ID 完全一致
5. 点击"测一测"→ 题目 ID 也应该与 `data/quiz.json` 中的 ID 一致

**预期结果**：✅ 前端显示的 ID 与 JSON 中的 ID 一致

---

### Fix 3: 迁移路径灵活性 ✅
**场景**：后端启动时自动扫描 `data/` 目录下的 JSON，迁移到数据库

**测试步骤**：
1. 查看后端启动日志：`cat /tmp/finrookie.log` 或服务器 `~/fr-backend.log`
2. 查看是否有日志行如 `[OK] Card: ...`、`[OK] Quiz: ...` 等
3. 确认至少迁移了 ≥20 张知识卡（来自 `knowledge-cards.json`）
4. 数据库中验证（如果能访问后端）：
   ```bash
   curl http://127.0.0.1:8091/api/content/list  # 返回所有非删除内容
   ```
   应该返回 JSON 数组，包含所有迁移的卡片/题目

**预期结果**：✅ 启动时自动迁移，日志显示成功

---

### Fix 4: Admin 环境变量密码 ✅
**场景**：Admin 账号密码从环境变量读取，若未设置则生成临时密码

**测试步骤**：
1. 查看后端启动日志：`cat /tmp/finrookie.log` 或服务器日志
2. 应该看到类似：
   ```
   [WARNING] Admin account 'admin' created with temporary password.
             Set ADMIN_PASSWORD environment variable for production use.
   ```
3. 尝试用默认账号 `admin` 登录后台（如果有 /admin）
4. 如果设置了 `ADMIN_PASSWORD` 环境变量，不应该看到 WARNING，密码来自变量
5. 验证密码没有硬编码在代码中：
   ```bash
   grep -r "admin123" backend/  # 不应该有结果
   grep -r "CHANGE_ME_" backend/  # 只在 admin.py 的临时密码生成处
   ```

**预期结果**：✅ 启动时有 WARNING / ✅ 密码来自环境变量 / ✅ 没有硬编码密码

---

## 综合验证

完成上述 4 项测试后，汇总结果：

| 功能 | 本地 ✅/❌ | 服务器 ✅/❌ | 备注 |
|------|----------|----------|------|
| Soft Delete | | | |
| 稳定 ID | | | |
| 迁移路径 | | | |
| Admin 密码 | | | |

**有问题时**：
- 提供具体症状（如"卡片 ID 不一致"、"删除后还能看到"等）
- 附上浏览器控制台错误或后端日志
- 我会诊断并修复
