<!-- 早报自动更新诊断与修复指南 -->
# FinRookie 早报自动更新诊断报告

## 📋 问题现象
- ❌ 每次清完缓存点进来，早报内容总是一样的（7月31日）
- ❌ 用户以为是缓存问题，但实际上是数据未更新

## 🔍 根本原因

早报的自动化流程**链条断裂在最源头**：

### 应该的流程（目前无法工作）
```
Windows Task Scheduler 定时触发
        ↓
daily_update.sh (控制脚本)
        ↓
fetch_headlines.py (抓取新闻源)
        ↓
raw/headlines-{date}.json (中间数据)
        ↓
ai_rewrite.py (AI改写成早报)
        ↓
data/briefings/{date}.json (最终早报)
        ↓
前端加载 → 用户看到最新早报
```

### 当前状态
❌ **Windows Task Scheduler 中没有注册定时任务**
- 所以 daily_update.sh 从未执行
- 所以 fetch_headlines.py 从未执行
- 所以 ai_rewrite.py 从未执行
- 所以 data/briefings/ 中没有新的早报文件
- 所以前端只能读到 7月31日的早报

## ✅ 修复方案

### 步骤1：运行 PowerShell 脚本配置定时任务

1. **用管理员权限打开 PowerShell**
   - Win+X → Windows PowerShell(管理员)

2. **运行配置脚本**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   C:\Users\86184\finrookie\pipeline\setup_schedule.ps1
   ```

3. **验证任务创建成功**
   ```powershell
   Get-ScheduledTask -TaskName "FinRookie-DailyBriefingUpdate"
   ```

### 步骤2：验证生效

配置完成后，会在以下时间自动执行：
- **每天 00:00**（午夜）- 主要更新时段
- **每天 06:00**（上午6点）- 备份更新时段

日志位置：`C:\Users\86184\finrookie\pipeline\cron.log`

## 🧪 手动测试

如果不想等到定时时间，可以手动触发一次：

```powershell
# 运行更新脚本
C:\Users\86184\finrookie\pipeline\daily_update.sh

# 或通过 bash
bash.exe -c "C:\Users\86184\finrookie\pipeline\daily_update.sh"
```

## 📊 效果检查

1. 打开浏览器，访问 FinRookie
2. 清除缓存（Ctrl+Shift+Delete）
3. 刷新页面，进入"早报"tab
4. 应该能看到**今天日期的早报**，而不是7月31日

## 🛠️ 故障排除

### 脚本运行报错：找不到 ai.env
**原因**：AI API 配置文件缺失  
**解决**：需要在 `~/finrookie-secret/ai.env` 中配置 API 秘钥

### 脚本运行报错：网络连接问题
**原因**：无法连接到新闻源  
**解决**：检查网络连接，或修改 fetch_headlines.py 中的数据源

### 任务显示但不执行
**原因**：可能需要重启系统以激活任务  
**解决**：
```powershell
# 手动启动任务
Start-ScheduledTask -TaskName "FinRookie-DailyBriefingUpdate"
```

## 🎯 长期方案

当前是**本地开发环境**的解决方案。如果要部署到**正式服务器**：

```bash
# 在 Linux/Mac 上配置 cron
(crontab -l 2>/dev/null || echo ""; \
 echo "0 0 * * * /home/user/finrookie/pipeline/daily_update.sh"; \
 echo "0 6 * * * /home/user/finrookie/pipeline/daily_update.sh") | crontab -
```

---
**诊断日期**：2026-08-03  
**问题等级**：🔴 高（影响用户体验）  
**修复难度**：🟢 低（一键配置）
