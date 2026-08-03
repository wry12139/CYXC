#!/bin/bash
# 财小白 · 每日自动更新(cron 调用)
# 依次:抓头条 -> AI改写早报 -> 生成延伸阅读。任一步失败即停,不用旧数据生成。
# 日志:~/finrookie-app/pipeline/cron.log;单实例:flock 防重入。
set -euo pipefail

APP="$HOME/finrookie-app"
LOG="$APP/pipeline/cron.log"
LOCK="$APP/pipeline/.daily.lock"
TS() { date '+%Y-%m-%d %H:%M:%S'; }

# 防重入:拿不到锁说明已有实例在跑,直接退出
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "$(TS) [SKIP] 已有实例在运行,本次跳过" >> "$LOG"
  exit 0
fi

log() { echo "$(TS) $*" >> "$LOG"; }

# 日志轮转放在开头(持锁状态下,无并发写风险)
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 500 ]; then
  tail -n 300 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

log "==================== 开始 ===================="
cd "$APP" || { log "[ERR] 进不去 $APP"; exit 1; }

log "[1/3] 抓取头条..."
if ! python3 pipeline/fetch_headlines.py >> "$LOG" 2>&1; then
  log "[ERR] 抓取失败(退出码非0),终止,不进行AI改写(避免用旧数据生成)"
  exit 1
fi

log "[2/3] AI改写早报..."
if ! python3 pipeline/ai_rewrite.py >> "$LOG" 2>&1; then
  log "[ERR] AI改写失败(退出码非0);原有早报保持不变"
  exit 1
fi

log "[3/3] 生成延伸阅读..."
if ! python3 pipeline/ai_generate_articles.py >> "$LOG" 2>&1; then
  log "[WARN] 延伸阅读生成失败,但早报已成功生成"
fi

log "[OK] 完成"
