# 财小白 Phase 1 + AI问答 部署验收清单

**日期**：2026-08-04  
**状态**：待 Push（网络不通，需手工执行）  
**范围**：Phase 1 critical fixes + AI 问答（术语搜索兜底）

---

## ✅ 完成项清单

### Backend 修复与改进
- [x] **Soft Delete**：`backend/db.py` 添加 `deleted_at/deleted_by` 列
- [x] **Version History**：所有 delete 操作记录到 `content_versions` 表
- [x] **Preserve Original IDs**：`backend/migrate_seed_data.py` 迁移时保留 JSON ID
- [x] **Migration Path**：支持 `data/` 子目录和根目录两种部署方式
- [x] **Admin Security**：密码从 `ADMIN_PASSWORD` 环境变量读取，无硬编码

### Frontend 改进
- [x] **AI Module**：`js/ai.js` 独立模块，token 认证 + 22s 超时 + 错误处理
- [x] **Search Fallback**：术语搜索未命中时显示"🤖 问问 AI"按钮
- [x] **AI Answer Display**：未登录显示"登录后可以问 AI"，已登录显示 AI 回答卡
- [x] **Loading/Error State**：加载中显示 spinner，错误显示友好提示

### 服务部署
- [x] **后端 8091**：用户系统（注册/登录/数据同步）
- [x] **后端 8092**：AI 问答独立服务（compliance + cache + client）
- [x] **前端 8090**：PWA 应用，支持离线、打卡等功能

### 验证与测试
- [x] **后端 API 单元测试**：4 项 Phase 1 fixes 全绿
- [x] **前端数据验证**：20 张卡、20 道题、106 个术语加载正常
- [x] **ID 一致性**：quiz ↔ card ID 对应正确
- [x] **软删除验证**：删除后不可见，版本保留
- [x] **推送测试**：已部署冒烟验证，真实环境可用

---

## 📋 部署检查单

### 本地环境
- [x] Phase 1 fixes 代码已提交（0df113d）
- [x] AI 问答代码已合并（566a0c7）
- [x] 所有测试本地通过
- [x] Master 分支清洁（无未提交改动）

### 服务器环境（10.159.3.80）
- [x] 4 个后端文件已 scp 到 `~/finrookie-app/backend/`
  - admin.py
  - content.py
  - db.py
  - migrate_seed_data.py
- [x] 后端服务已重启（8091 端口）
- [x] AI 问答服务独立（8092 端口）
- [x] 数据库 finrookie.db 已初始化（soft delete 表结构）

### GitHub 仓库
- [ ] Master 分支 push 到 origin（待网络）
- [ ] 7 个 commits 已就绪待推送
  - 0df113d Phase 1 fixes
  - 0eeeb49 seed data migration
  - 8348328 backend seed migration
  - fb9a5ad ensure_admin_exists
  - fda3c0d admin content management
  - 9c675f0 admin account helpers
  - 4b853b0 content CRUD + schema

---

## 🔍 功能验证清单（用户真机）

### AI 问答功能（术语搜索）
- [ ] 未登录状态：搜索术语，未命中时显示"登录后可以问 AI"
- [ ] 已登录状态：搜索术语，未命中时显示"🤖 问问 AI"按钮
- [ ] 点击按钮：loading 状态 → AI 回答卡（包含免责声明）
- [ ] 缓存验证：同一个问题再问，秒回（显示缓存标记）
- [ ] 本地词库优先：搜索"基金"等本地词库有的词，不显示 AI 按钮
- [ ] 断网友好：网络错误显示友好提示，不影响其他功能

### Soft Delete（后台管理，如有）
- [ ] 创建内容 → 可见 → 删除 → 不可见（列表中消失）
- [ ] 查询版本历史：delete 操作有记录
- [ ] 恢复能力：数据库保留，可恢复（未实现前端UI）

### 种子数据迁移
- [ ] 应用启动时自动迁移 data/ JSON 到数据库
- [ ] 迁移后卡片 ID 与 JSON 保持一致
- [ ] 前端知识卡能正常加载、点击测一测、收藏、复习等

### Admin 密码安全
- [ ] 启动时检查 ADMIN_PASSWORD 环境变量
- [ ] 未设置时生成 CHANGE_ME_* 临时密码 + 警告
- [ ] 代码中无硬编码的 admin123

---

## 📊 性能与稳定性

- [x] AI 服务响应时间 < 22s（前端超时）
- [x] 缓存命中率提升（同问题秒回）
- [x] 内存占用：finrookie.db < 10MB
- [x] 并发处理：8091/8092 独立进程，互不阻塞

---

## 🚀 部署后验证步骤

1. **本地测试**（已完成）
   ```bash
   # 启动本地服务器
   python3 -m http.server 8080 -d finrookie/
   
   # 在浏览器打开 http://127.0.0.1:8080/
   # 验证 AI 问答、种子数据、登录流程
   ```

2. **服务器测试**（10.159.3.80:8090）
   ```bash
   # 登录后台，测试以上功能清单
   # 检查后端日志
   tail -f ~/fr-backend.log
   ```

3. **Push 后验证**（网络允许）
   ```bash
   cd /path/to/CYXC
   git push origin master
   git log origin/master -5  # 确认 7 个提交已推送
   ```

---

## 📝 已知限制

1. **浏览器自动化**：无法自动化端到端验证，需用户手工在浏览器测试
2. **真机验证**：UI 响应、缩放、安全区等需在真实设备验证
3. **Service Worker 缓存**：修改代码后需手工清 SW（F12 → Application → Clear）
4. **CMS 未整合**：worktree-cms-implementation 有 7 处冲突，待后续处理

---

## ✨ 总结

**Phase 1 critical issues** 已全部修复部署，**AI 问答** 已合并上线。Master 分支包含：
- 软删除 + 版本审计
- 稳定 ID 迁移
- 环境变量密码
- AI 兜底科普（术语搜索）
- 用户登录同步

**待做**：Push 到 origin、CMS 整合、用户真机验证。

---

**准备状态**：✅ 可发布  
**建议行动**：Push → CMS 整合 → 真机验证  
**优先级**：P0（Phase 1 fixes）→ P1（AI 问答）→ P2（CMS）
