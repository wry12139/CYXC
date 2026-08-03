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
    """从 AI 回复里抽出 JSON 对象，容错各种格式问题。"""
    text = text.strip()
    # 去掉 ```json``` 包裹
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()

    # 找第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("未找到JSON对象")

    json_str = text[start:end + 1]

    # 第一次尝试：直接解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 第二次：清理格式问题
    # 1. 去掉真实的换行/制表符(JSON内不应该有)
    json_str = re.sub(r'[\r\n\t]+', ' ', json_str)
    # 2. 多个空格变一个
    json_str = re.sub(r' +', ' ', json_str)
    # 3. 中文引号替换成英文
    json_str = json_str.replace('"', '"').replace('"', '"')
    json_str = json_str.replace(''', "'").replace(''', "'")
    # 4. 修复常见的转义问题(\x → x, \' → ')
    json_str = re.sub(r'\\([^"\\u])', r'\1', json_str)
    # 5. 修复孤立的反斜线(不在转义序列中)
    json_str = re.sub(r'(?<=[^\\])\\ +', ' ', json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # 最后尝试：如果还是失败，尝试手工修复一些常见问题
        # 如 "body":"<p>...</p>" 变成 "body": "<p>...</p>"(多余空格)
        json_str = re.sub(r'": +', '": ', json_str)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e2:
            print(f"[DEBUG] JSON解析最终失败。错误:{e}。原始前300字:{json_str[:300]}")
            raise ValueError(f"JSON解析失败:{e}") from e2


def has_banned(text):
    return [w for w in BANNED if w in text]


def gen_article_for_briefing_item(item, glossary, retry_count=0, max_retries=2):
    """
    为单条早报生成延伸阅读文章。支持重试。
    输入: 早报条目 {title, summary, plain, terms}
    输出: {title, body, topic} 或 None
    """
    terms_hint = "、".join(item.get("terms", []))
    terms_all = "、".join(list(glossary.keys())[:50])

    prompt = f"""基于这条财经要闻,生成一篇200-300字的新手讲解文章。

要闻: {item['title']}
摘要: {item['summary']}
新手解读: {item['plain']}

要求:
1. 白话讲解"这件事的背景、普通人的影响、需要注意什么"
2. 必须是2-3个段落,每段用 <p>...</p> 包裹。段落内容用单行文本,不要断行。
3. 关键词用 <span data-term="术语名">术语名</span> 标记。术语名从这个列表选:{terms_all}
4. 字数严格200-300字(含标签)
5. **严禁**:直接推荐买卖(如"应该买入XX")、涨跌预测、荐股。允许讲解概念和风险。
6. 主题从[basics,fund,stock,insurance,avoid_pit]选最相关的1个
7. **输出必须是单行JSON**(换行都用空格代替),格式:
{{"title":"简短标题(20字内)","body":"<p>...</p><p>...</p>","topic":"basics"}}
必须用英文双引号。只输出JSON,不要任何其他文字。"""

    try:
        text = call_ai(prompt, max_tokens=1500)
        obj = extract_json(text)
    except Exception as e:
        if retry_count < max_retries:
            print(f"[文章] #{retry_count+1}次重试 {item['title'][:20]}...")
            return gen_article_for_briefing_item(item, glossary, retry_count+1, max_retries)
        print(f"[文章] 放弃({item['title'][:20]}...): {e}")
        return None

    if not isinstance(obj, dict):
        if retry_count < max_retries:
            print(f"[文章] #{retry_count+1}次重试 {item['title'][:20]}...")
            return gen_article_for_briefing_item(item, glossary, retry_count+1, max_retries)
        print(f"[文章] 返回不是JSON对象({item['title'][:20]}...)")
        return None

    # 校验和过滤
    title = obj.get("title", "").strip()
    body = obj.get("body", "").strip()
    topic = obj.get("topic", "").strip()

    if not all([title, body, topic]):
        if retry_count < max_retries:
            print(f"[文章] #{retry_count+1}次重试 {item['title'][:20]}...")
            return gen_article_for_briefing_item(item, glossary, retry_count+1, max_retries)
        print(f"[文章] 必填字段缺失({item['title'][:20]}...)")
        return None

    if topic not in TOPICS:
        print(f"[文章] 非法topic'{topic}'({item['title'][:20]}...)")
        return None

    # 术语校验
    term_pattern = r'<span data-term="([^"]+)">([^<]+)</span>'
    matched_terms = re.findall(term_pattern, body)
    bad_terms = [t for t, _ in matched_terms if t not in glossary]
    if bad_terms:
        print(f"[文章] 孤儿术语{bad_terms}({item['title'][:20]}...)")
        return None

    # 合规检查:严禁直接荐股或预测
    # 允许: "投资者", "买入", "卖出" 在讲解/风险语境中
    # 禁止: "应该买入", "必须卖出", "一定会涨", "目标价"
    strict_banned = [
        "应该买入", "应该卖出", "必须买入", "必须卖出",
        "一定会涨", "一定会跌", "必涨", "必跌",
        "牛股", "黑马", "翻倍", "目标价",
        "荐股", "推荐股票", "金股",
    ]
    blob = title + body
    bad = [w for w in strict_banned if w in blob]
    if bad:
        if retry_count < max_retries:
            print(f"[文章] #{retry_count+1}次重试({bad}) {item['title'][:20]}...")
            return gen_article_for_briefing_item(item, glossary, retry_count+1, max_retries)
        print(f"[文章] 违规词{bad}({item['title'][:20]}...)")
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
