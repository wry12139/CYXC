#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财小白 · 财经头条抓取脚本(步骤3:先只抓不改写)
- 多源可配置(RSS)
- 解析标题/链接/时间/摘要
- 跨源去重(按标题)
- 存成结构化 raw JSON,供后续 AI 改写用
纯标准库实现,服务器 python3 可独立运行,不依赖第三方包。
"""
import urllib.request
import ssl
import json
import os
import sys
import re
import tempfile
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

# ---- 配置:抓取源(已在本机验证可用)----
SOURCES = [
    {"name": "东方财富", "url": "http://rss.eastmoney.com/rss_partener.xml"},
    {"name": "华尔街见闻", "url": "https://dedicated.wallstreetcn.com/rss.xml"},
    {"name": "36氪", "url": "https://36kr.com/feed"},
    {"name": "人民网财经", "url": "http://www.people.com.cn/rss/finance.xml"},
]

MAX_PER_SOURCE = 15          # 每源最多取多少条(取最新)
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
CN_TZ = timezone(timedelta(hours=8))

# TLS 默认验证(不再关闭:抓来的内容会进入 AI 改写并对用户展示,须防中间人伪造)
_ctx = ssl.create_default_context()


def _atomic_write_json(path, obj):
    """原子写:先写同目录临时文件再 os.replace,避免中断留下半截文件"""
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _norm_title(t):
    """标题归一化用于去重:去首尾空白、去【】[]()括注、压缩空白、转小写"""
    t = re.sub(r"[【\[(（].*?[】\])）]", "", t)
    t = re.sub(r"\s+", "", t)
    return t.lower()


def _clean(text):
    """去 HTML 标签、压缩空白"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _text(elem, tag):
    child = elem.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def fetch_source(src):
    """抓单个 RSS 源,返回条目列表"""
    items = []
    try:
        req = urllib.request.Request(src["url"], headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=15, context=_ctx).read()
        root = ET.fromstring(raw)
        # RSS 2.0: channel/item
        for item in root.iter("item"):
            title = _clean(_text(item, "title"))
            if not title:
                continue
            items.append({
                "source": src["name"],
                "title": title,
                "link": _text(item, "link"),
                "pubDate": _text(item, "pubDate"),
                "summary": _clean(_text(item, "description"))[:200],
            })
            if len(items) >= MAX_PER_SOURCE:
                break
        return items, None
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:80]}"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    now = datetime.now(CN_TZ)
    all_items = []
    report = []
    for src in SOURCES:
        items, err = fetch_source(src)
        if err:
            report.append(f"[FAIL] {src['name']}: {err}")
        else:
            report.append(f"[OK]   {src['name']}: {len(items)} 条")
            all_items.extend(items)

    # 跨源去重:按归一化标题
    seen = set()
    deduped = []
    for it in all_items:
        key = _norm_title(it["title"])
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    # 控制台报告(先打,便于诊断)
    print("=== 抓取报告 " + now.strftime("%Y-%m-%d %H:%M:%S") + " ===")
    for line in report:
        print(line)

    # 零条目:不写文件,退出非零,让 wrapper 停止后续 AI 步骤(避免用旧数据生成)
    if not deduped:
        print("[ERR] 所有源均无有效条目,不写文件,退出。")
        sys.exit(1)

    out = {
        "fetchedAt": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "sourceCount": len(SOURCES),
        "itemCount": len(deduped),
        "items": deduped,
    }
    date_str = now.strftime("%Y-%m-%d")
    out_path = os.path.join(OUT_DIR, f"headlines-{date_str}.json")
    _atomic_write_json(out_path, out)

    print(f"去重后共 {len(deduped)} 条,已写入 {out_path}")


if __name__ == "__main__":
    main()
