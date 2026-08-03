#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财小白 · 延伸阅读自动生成脚本(步骤5)
读取当天生成的早报 -> 为每条热点调 AI 生成 200-300 字讲解文章 -> 合并到 articles.json
内置合规过滤 + 格式校验 + 术语校验。
配置从 ~/finrookie-secret/ai.env 读取。
"""
import urllib.request
import ssl
import json
import os
import sys
import re
import tempfile
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(APP_DIR, "data")
SECRET = os.path.expanduser("~/finrookie-secret/ai.env")
CN_TZ = timezone(timedelta(hours=8))

_ctx = ssl.create_default_context()

# 合规红线(与 ai_rewrite.py 同步)
BANNED = [
    "买入", "卖出", "加仓", "减仓", "抄底", "追高", "建仓", "清仓", "满仓", "梭哈",
    "买它", "值得买入", "可买", "可入", "上车",
    "推荐股票", "荐股", "目标价", "牛股", "翻倍", "黑马", "潜力股", "首选", "金股",
    "必涨", "必跌", "涨停板", "稳赚", "包赚", "一定会涨", "一定会跌", "稳赢", "保本高息",
    "预测", "内幕", "可关注", "逢低布局", "逢低吸纳", "看多", "看空", "上行空间",
    "建议持有", "短线机会", "重点关注个股", "低吸", "高抛",
]

TOPICS = ["basics", "fund", "stock", "avoid_pit", "insurance"]
REQUIRED_CFG = ("FR_AI_KEY", "FR_AI_BASE", "FR_AI_MODEL")


def load_cfg():
    cfg = {}
    if not os.path.exists(SECRET):
        print(f"[ERR] 配置文件不存在: {SECRET}")
        sys.exit(1)
    with open(SECRET, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    missing = [k for k in REQUIRED_CFG if not cfg.get(k)]
    if missing:
        print(f"[ERR] 配置缺少必填项: {missing}")
        sys.exit(1)
    return cfg


CFG = load_cfg()


def _atomic_write_json(path, obj):
    """原子写:临时文件 + fsync + os.replace"""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
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


def call_ai(prompt, max_tokens=1500, temperature=0.5, retry_count=0, max_retries=1):
    """调用 AI,返回文本。"""
    body = json.dumps({
        "model": CFG["FR_AI_MODEL"],
        "messages": [
            {"role": "system", "content": "你是面向中国金融小白的科普编辑。生成200-300字白话讲解,严禁推荐个股、预测涨跌、给出买卖建议。严格按要求的JSON格式输出。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(
        CFG["FR_AI_BASE"] + "/v1/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + CFG["FR_AI_KEY"], "Content-Type": "application/json"},
    )
    try:
        r = urllib.request.urlopen(req, timeout=90, context=_ctx)
        raw_resp = r.read().decode("utf-8", "replace")
        try:
            d = json.loads(raw_resp)
        except json.JSONDecodeError as e:
            print(f"[DEBUG] API 响应非法JSON: {e}。原始(前300字): {raw_resp[:300]}")
            raise ValueError(f"API 返回非法JSON: {e}") from e
        return d["choices"][0]["message"]["content"]
    except Exception as e:
        if retry_count < max_retries:
            print(f"[重试] AI调用失败,准备第{retry_count+2}次尝试: {e}")
            return call_ai(prompt, max_tokens, temperature, retry_count+1, max_retries)
        raise


def extract_json(text):
    """从 AI 回复里抽出 JSON 对象。"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("未找到顶层 JSON 对象")

    json_str = text[start:end + 1]

    try:
        obj = json.loads(json_str)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 清理中文引号和转义问题
    json_str_cleaned = json_str.replace('"', '"').replace('"', '"')  # 中文双引号
    json_str_cleaned = json_str_cleaned.replace("'", "'").replace("'", "'")  # 中文单引号
    json_str_cleaned = json_str_cleaned.replace("\\n", " ").replace("\\t", " ")  # 转义的换行符
    json_str_cleaned = re.sub(r'[\r\n\t]+', ' ', json_str_cleaned)  # 真实的换行符
    json_str_cleaned = re.sub(r' +', ' ', json_str_cleaned)  # 多个空格
    # 修复常见的转义问题(如 \escape 变成 escape)
    json_str_cleaned = re.sub(r'\\([^"\\])', r'\1', json_str_cleaned)

    try:
        obj = json.loads(json_str_cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError as e:
        print(f"[DEBUG] 清理后仍失败。错误: {e}。原始前200字: {json_str[:200]}")
        raise ValueError(f"JSON 解析失败: {e}") from e


def has_banned(text):
    return [w for w in BANNED if w in text]


def gen_article_for_briefing_item(item, glossary):
    """
    为单条早报生成延伸阅读文章。
    输入: 早报条目 {title, summary, plain, terms}
    输出: {title, body, topic} 或 None
    """
    terms_hint = "、".join(item.get("terms", []))
    terms_all = "、".join(list(glossary.keys())[:50])

    prompt = f"""基于这条财经要闻,生成一篇200-300字的新手讲解文章。

标题: {item['title']}
摘要: {item['summary']}
新手解读: {item['plain']}
相关术语: {terms_hint if terms_hint else '(无)'}

要求:
1. 用通俗白话讲清楚"这件事的背景是什么、对普通人理财的影响、需要注意什么"。
2. 分2-3个自然段,每段用<p>...</p>包裹。
3. 关键词必须用 <span data-term="术语名">术语名</span> 标记(注意 data-term 属性用英文双引号)。术语名从这个列表选:{terms_all}
4. 文字在200-300字之间。
5. 严禁买卖建议、涨跌预测、推荐个股。
6. 确定文章的主题(topic),从 [basics, fund, stock, insurance, avoid_pit] 中选一个最相关的。
7. 返回严格的 JSON 对象,格式(注意要用英文双引号,不要中文引号,所有特殊字符转义):
{{"title":"...","body":"<p>...</p>","topic":"basics"}}
只输出 JSON,不要任何多余文字或换行。"""

    try:
        text = call_ai(prompt, max_tokens=1500)
        obj = extract_json(text)
    except Exception as e:
        print(f"[文章] AI调用/解析失败({item['title'][:20]}...): {e}")
        return None

    if not isinstance(obj, dict):
        print(f"[文章] 返回不是 JSON 对象({item['title'][:20]}...)")
        return None

    # 校验和过滤
    title = obj.get("title", "").strip()
    body = obj.get("body", "").strip()
    topic = obj.get("topic", "").strip()

    if not all([title, body, topic]):
        print(f"[文章] 必填字段缺失({item['title'][:20]}...)")
        return None

    if topic not in TOPICS:
        print(f"[文章] 非法 topic '{topic}'({item['title'][:20]}...)")
        return None

    # 术语校验:body 中的所有 data-term 必须在 glossary
    term_pattern = r'<span data-term="([^"]+)">([^<]+)</span>'
    matched_terms = re.findall(term_pattern, body)
    bad_terms = [t for t, _ in matched_terms if t not in glossary]
    if bad_terms:
        print(f"[文章] 含孤儿术语{bad_terms}({item['title'][:20]}...)")
        return None

    # 合规检查
    blob = title + body
    bad = has_banned(blob)
    if bad:
        print(f"[文章] 含违规词{bad}({item['title'][:20]}...)")
        return None

    return {
        "title": title[:30],
        "body": body,
        "topic": topic,
    }


def load_briefing_for(date_str):
    """读取指定日期的早报。"""
    path = os.path.join(DATA_DIR, "briefings", f"{date_str}.json")
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[ERR] 早报文件解析失败: {e}")
        return None


def main():
    now = datetime.now(CN_TZ)
    date_str = now.strftime("%Y-%m-%d")

    briefing = load_briefing_for(date_str)
    if not briefing:
        print(f"[文章] 无今日({date_str})早报,跳过文章生成")
        return

    glossary = json.load(open(os.path.join(DATA_DIR, "glossary.json"), encoding="utf-8"))
    articles_path = os.path.join(DATA_DIR, "articles.json")

    # 读现有文章
    try:
        existing = json.load(open(articles_path, encoding="utf-8"))
    except Exception as e:
        print(f"[ERR] articles.json 读取失败: {e}")
        return

    print(f"=== 延伸阅读生成 {date_str}(早报 {len(briefing['items'])} 条) ===")

    # 为每条早报生成文章
    new_articles = []
    for i, item in enumerate(briefing["items"], 1):
        article = gen_article_for_briefing_item(item, glossary)
        if article:
            # 给文章添加 ID 和来源信息
            article_id = f"a{len(existing) + len(new_articles) + 1:03d}"
            article["id"] = article_id
            article["date"] = date_str
            article["source_title"] = item["title"]
            new_articles.append(article)
            print(f"[文章] #{i} {item['title'][:30]}... -> {article['topic']}")
        else:
            print(f"[文章] #{i} {item['title'][:30]}... (被过滤或失败)")

    if not new_articles:
        print(f"[文章] 本轮未产出任何文章")
        return

    # 合并到既有文章
    existing.extend(new_articles)

    try:
        _atomic_write_json(articles_path, existing)
        print(f"[文章] 已生成 {len(new_articles)} 篇 -> {articles_path}(共 {len(existing)} 篇)")
    except Exception as e:
        print(f"[ERR] 写入 articles.json 失败: {e}")
        return

    print("=== 完成 ===")


if __name__ == "__main__":
    main()
