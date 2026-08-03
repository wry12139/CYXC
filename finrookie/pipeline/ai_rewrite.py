#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财小白 · AI 改写脚本(步骤4)
读取抓取的头条 raw JSON -> 调 AI 改写成:
  1) 每日早报(briefings/YYYY-MM-DD.json)
  2) 新知识卡(追加到 knowledge-cards.json)
  3) 新题目(追加到 quiz.json)
内置合规过滤 + 格式校验:不合格自动丢弃,保护"全自动上线"。
配置从 ~/finrookie-secret/ai.env 读取(FR_AI_KEY/FR_AI_BASE/FR_AI_MODEL)。
纯标准库实现,服务器 python3 可独立运行。
"""
import urllib.request
import ssl
import json
import os
import sys
import re
import tempfile
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../pipeline
APP_DIR = os.path.dirname(BASE_DIR)                             # .../finrookie-app
DATA_DIR = os.path.join(APP_DIR, "data")
RAW_DIR = os.path.join(BASE_DIR, "raw")
SECRET = os.path.expanduser("~/finrookie-secret/ai.env")
CN_TZ = timezone(timedelta(hours=8))

# TLS 默认验证(不再关闭:AI 返回内容会无审核直接对用户展示,须防中间人伪造)
_ctx = ssl.create_default_context()

# 早报最少保留条数:低于此值视为异常(模型漂移/大面积被过滤),整轮不发布
MIN_ITEMS = 3

# ---- 合规红线:出现这些词的生成内容直接丢弃 ----
BANNED = [
    # 直接买卖动作
    "买入", "卖出", "加仓", "减仓", "抄底", "追高", "建仓", "清仓", "满仓", "梭哈",
    "买它", "值得买入", "可买", "可入", "上车",
    # 荐股 / 目标价
    "推荐股票", "荐股", "目标价", "牛股", "翻倍", "黑马", "潜力股", "首选", "金股",
    # 预测涨跌 / 稳赚
    "必涨", "必跌", "涨停板", "稳赚", "包赚", "一定会涨", "一定会跌", "稳赢", "保本高息",
    # 常见诱导措辞
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
    """原子写:临时文件 + fsync + os.replace,避免中断留下半截文件"""
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


def call_ai(prompt, max_tokens=2000, temperature=0.5, retry_count=0, max_retries=1):
    """调用 AI,返回文本。失败抛异常。支持重试。"""
    body = json.dumps({
        "model": CFG["FR_AI_MODEL"],
        "messages": [
            {"role": "system", "content": "你是面向中国金融小白的科普编辑。只做名词解释和风险科普,严禁推荐个股、预测涨跌、给出买卖建议。语言通俗、准确、克制。严格按要求的JSON格式输出,不要多余文字。"},
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
    """从 AI 回复里抽出 JSON 数组(容错 ```json 包裹)。要求顶层是数组。"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()

    # 只接受顶层数组:从第一个 [ 到与之匹配的最后一个 ]
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("未找到顶层 JSON 数组")

    json_str = text[start:end + 1]

    # 第一层:直接尝试
    try:
        obj = json.loads(json_str)
        if isinstance(obj, list):
            return obj
    except json.JSONDecodeError:
        pass

    # 第二层:清理中文引号和多余空格
    # 中文引号 " " " ' ' 替换成 ASCII 引号
    json_str_cleaned = json_str.replace('"', '"').replace('"', '"').replace("'", "'").replace("'", "'")
    # 多余的制表符和换行符替换成空格
    json_str_cleaned = re.sub(r'[\r\n\t]+', ' ', json_str_cleaned)
    # 多个空格变一个
    json_str_cleaned = re.sub(r' +', ' ', json_str_cleaned)

    try:
        obj = json.loads(json_str_cleaned)
        if isinstance(obj, list):
            return obj
    except json.JSONDecodeError as e:
        print(f"[DEBUG] 清理后仍失败。错误: {e}。原始前200字: {json_str[:200]}")
        raise ValueError(f"JSON 解析失败(已尝试清理): {e}") from e


def has_banned(text):
    return [w for w in BANNED if w in text]


def load_raw_for(date_str):
    """严格加载指定日期的 raw 文件,并校验其内部 date 一致(防用错日期的旧数据)"""
    path = os.path.join(RAW_DIR, f"headlines-{date_str}.json")
    if not os.path.exists(path):
        return None
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[ERR] raw 文件解析失败: {e}")
        return None
    if raw.get("date") != date_str:
        print(f"[ERR] raw 日期不匹配(文件内 {raw.get('date')} != 目标 {date_str}),拒绝使用")
        return None
    return raw


def gen_briefing(items, date_str):
    """精选头条 -> 每日早报。返回 briefing dict 或 None。"""
    # 取前 12 条标题+摘要喂给 AI 让它精选并改写
    lines = []
    for i, it in enumerate(items[:12]):
        lines.append(f"{i+1}. [{it['source']}] {it['title']} — {it.get('summary','')[:80]}")
    headlines = "\n".join(lines)
    glossary = json.load(open(os.path.join(DATA_DIR, "glossary.json"), encoding="utf-8"))
    terms = "、".join(list(glossary.keys())[:40])
    prompt = f"""下面是今天的财经头条。请挑选其中最适合金融小白了解的 5 条,改写成"新手版早报"。

头条列表:
{headlines}

要求:
1. 每条包含:title(精简标题,不超25字)、summary(客观概括,2句内)、plain(新手解读:用大白话讲清"这跟普通人有什么关系",2-3句,只科普不荐股不预测)、terms(从这些已有术语里挑0-2个相关的:{terms})
2. 严禁出现买卖建议、涨跌预测、推荐个股。
3. 重要:所有文本中不要使用中文引号、不要使用特殊符号,确保输出是有效的 JSON。
4. 严格输出 JSON 数组,格式:
[{{"title":"...","summary":"...","plain":"...","terms":["..."]}}]
只输出 JSON,不要任何多余文字或换行。每个字符串字段不要跨越多行。"""
    try:
        text = call_ai(prompt, max_tokens=2000)
        arr = extract_json(text)
    except Exception as e:
        print(f"[早报] AI调用/解析失败: {e}")
        return None
    if not isinstance(arr, list) or not arr:
        print("[早报] AI返回不是有效数组")
        return None
    # 合规 + 类型/格式校验,逐条过滤
    valid = []
    for it in arr:
        if not isinstance(it, dict):
            continue
        # 三个文本字段必须是非空字符串
        if not all(isinstance(it.get(k), str) and it.get(k).strip()
                   for k in ("title", "summary", "plain")):
            print(f"[早报] 丢弃字段类型/空值不合格的条目")
            continue
        # terms 必须是字符串列表(容错:非列表则视为空)
        raw_terms = it.get("terms", [])
        if not isinstance(raw_terms, list):
            raw_terms = []
        raw_terms = [t for t in raw_terms if isinstance(t, str)]
        # 合规:标题/概括/解读 + 所有 terms 一起查违规词
        blob = it["title"] + it["summary"] + it["plain"] + "".join(raw_terms)
        bad = has_banned(blob)
        if bad:
            print(f"[早报] 丢弃含违规词{bad}的条目: {it['title'][:20]}")
            continue
        # terms 只保留词库里真实存在的,且限长
        terms = [t for t in raw_terms if t in glossary][:3]
        valid.append({
            "title": it["title"].strip()[:40],
            "summary": it["summary"].strip(),
            "plain": it["plain"].strip(),
            "terms": terms,
        })
    if len(valid) < MIN_ITEMS:
        print(f"[早报] 通过校验仅 {len(valid)} 条,低于最低 {MIN_ITEMS} 条,整轮不发布")
        return None
    return {
        "date": date_str,
        "disclaimer": "本早报由AI辅助生成,仅供学习,不构成投资建议",
        "items": valid,
    }


def gen_cards(raw_items, date_str):
    """生成 2-3 张新知识卡 + 配套题目。返回 (cards_list, quizzes_list) 或 ([], [])。"""
    glossary = json.load(open(os.path.join(DATA_DIR, "glossary.json"), encoding="utf-8"))
    cards_path = os.path.join(DATA_DIR, "knowledge-cards.json")
    quiz_path = os.path.join(DATA_DIR, "quiz.json")

    # 读现有卡片和题目,计算下一个 ID
    try:
        existing_cards = json.load(open(cards_path, encoding="utf-8"))
        existing_quizzes = json.load(open(quiz_path, encoding="utf-8"))
    except Exception as e:
        print(f"[卡片] 读取现有卡片失败: {e}")
        return [], []

    next_card_id_num = len(existing_cards) + 1
    next_quiz_id_num = len(existing_quizzes) + 1

    # 统计主题分布,按不足的主题引导 AI
    topic_count = {}
    for card in existing_cards:
        for topic in card.get("topics", []):
            topic_count[topic] = topic_count.get(topic, 0) + 1

    # 均衡提示:优先补充落后的主题
    topic_order = ["stock", "fund", "insurance", "avoid_pit", "basics"]
    underfunded = [t for t in topic_order if topic_count.get(t, 0) < 5][:2]
    topic_hint = "、".join(underfunded) if underfunded else "任意"

    terms = "、".join(list(glossary.keys())[:50])
    prompt = f"""基于财经头条,生成 2-3 张新手金融教育卡片。

头条摘要(前5条):
{chr(10).join([f"- {it['title']}" for it in raw_items[:5]])}

要求:
1. 每张卡包含 4 个字段:
   - title: 卡片标题(5-10字,例如"股票缩量什么意思")
   - body: HTML 内容,2-3个段落。每段用<p>...</p>包裹。关键词必须用<span data-term="术语名">术语名</span>标记(注意:术语名必须同时出现在 span 标签的 data-term 和文本内容中)。例如:<p>买<span data-term="基金">基金</span>时要注意费率。</p>
   - difficulty: L1 或 L2 或 L3
   - topics: 字符串数组,从[basics, fund, stock, insurance, avoid_pit]中选 1-2 个,优先选 {topic_hint}
   - quiz: 对象,包含 stem(问题)、options(3个选项数组)、answer(正确答案索引 0/1/2)、explain(解释)

2. 术语只能从这里选:{terms}
3. 避免与早报重复。
4. HTML body 必须闭合每个<span>标签:❌错误(<span data-term="术语">错)  ✓正确(<span data-term="术语">术语</span>)
5. 严格输出 JSON 数组,每个元素都有 title/body/difficulty/topics/quiz 五个字段。不要任何多余文字或换行。

输出范例:
[{{"title":"基金定投如何操作","body":"<p>定投就是<span data-term=\"定投\">定投</span>每月固定金额。</p><p>这样可以分散风险。</p>","difficulty":"L1","topics":["fund","basics"],"quiz":{{"stem":"为什么定投能降低风险?","options":["因为涨跌互补","因为本金更多","因为基金公司承诺"],"answer":0,"explain":"定投在高点少买、低点多买,平均成本被摊平。"}}}}]

严格按上面的格式输出。"""

    try:
        text = call_ai(prompt, max_tokens=2000)
        arr = extract_json(text)
    except Exception as e:
        print(f"[卡片] AI调用/解析失败: {e}")
        return [], []

    if not isinstance(arr, list) or not arr:
        print("[卡片] AI返回不是有效数组")
        return [], []

    # 校验和过滤
    valid_cards = []
    valid_quizzes = []

    for it in arr:
        if not isinstance(it, dict):
            continue

        # 必填字段检查
        title = it.get("title", "").strip()
        body = it.get("body", "").strip()
        difficulty = it.get("difficulty", "").strip()
        topics = it.get("topics", [])
        quiz = it.get("quiz", {})

        if not all([title, body, difficulty, topics, quiz]):
            print(f"[卡片] 丢弃必填字段缺失的条目")
            continue

        # 难度校验
        if difficulty not in ["L1", "L2", "L3"]:
            print(f"[卡片] 丢弃非法难度: {difficulty}")
            continue

        # 主题校验
        if not isinstance(topics, list) or not all(t in TOPICS for t in topics):
            print(f"[卡片] 丢弃主题格式/内容不合格")
            continue

        # 题目校验:必须有 stem/options/answer
        stem = quiz.get("stem", "").strip()
        options = quiz.get("options", [])
        answer = quiz.get("answer")

        if not stem or not isinstance(options, list) or len(options) < 3 or not isinstance(answer, int) or answer < 0 or answer >= len(options):
            print(f"[卡片] 丢弃题目格式不合格")
            continue

        # 术语校验:body 中的所有 data-term 必须在 glossary
        term_pattern = r'<span data-term="([^"]+)">([^<]+)</span>'
        matched_terms = re.findall(term_pattern, body)
        bad_terms = [t for t, _ in matched_terms if t not in glossary]
        if bad_terms:
            print(f"[卡片] 丢弃含孤儿术语{bad_terms}的条目")
            continue

        # 合规:卡片和题目的所有文本一起查违规词
        blob = title + body + stem + "".join(options)
        bad = has_banned(blob)
        if bad:
            print(f"[卡片] 丢弃含违规词{bad}的条目: {title[:20]}")
            continue

        # 通过校验,生成记录
        card_id = f"c{next_card_id_num:03d}"
        quiz_id = f"q{next_quiz_id_num:03d}"

        valid_cards.append({
            "id": card_id,
            "title": title[:30],
            "body": body,
            "difficulty": difficulty,
            "topics": topics,
            "quizIds": [quiz_id],
        })

        valid_quizzes.append({
            "id": quiz_id,
            "cardId": card_id,
            "type": "single",
            "stem": stem[:150],
            "options": options,
            "answer": answer,
            "explain": quiz.get("explain", "").strip()[:200] or "正确答案如上。",
        })

        next_card_id_num += 1
        next_quiz_id_num += 1

    return valid_cards, valid_quizzes


def main():
    now = datetime.now(CN_TZ)
    date_str = now.strftime("%Y-%m-%d")
    raw = load_raw_for(date_str)
    if not raw or not raw.get("items"):
        print(f"无今日({date_str})抓取数据,先运行 fetch_headlines.py")
        sys.exit(1)
    print(f"=== AI改写 {date_str}(源:{raw.get('itemCount')}条头条)===")

    # 1) 生成早报
    briefing = gen_briefing(raw["items"], date_str)
    if briefing:
        out = os.path.join(DATA_DIR, "briefings", f"{date_str}.json")
        _atomic_write_json(out, briefing)
        print(f"[早报] 已生成 {len(briefing['items'])} 条 -> {out}")
    else:
        print("[早报] 本轮未产出(全部被过滤或调用失败),保留原有早报不覆盖")

    # 2) 生成知识卡 / 题目
    cards, quizzes = gen_cards(raw["items"], date_str)
    if cards and quizzes:
        # 追加到既有文件
        cards_path = os.path.join(DATA_DIR, "knowledge-cards.json")
        quiz_path = os.path.join(DATA_DIR, "quiz.json")

        existing_cards = json.load(open(cards_path, encoding="utf-8"))
        existing_quizzes = json.load(open(quiz_path, encoding="utf-8"))

        existing_cards.extend(cards)
        existing_quizzes.extend(quizzes)

        _atomic_write_json(cards_path, existing_cards)
        _atomic_write_json(quiz_path, existing_quizzes)

        print(f"[卡片] 已生成 {len(cards)} 张新卡 -> {cards_path}")
    else:
        print("[卡片] 本轮未产出(被过滤或调用失败),保留既有卡片")

    print("=== 完成 ===")


if __name__ == "__main__":
    main()
