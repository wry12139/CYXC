import os, ssl, json, urllib.request

SECRET = os.path.expanduser("~/finrookie-secret/ai.env")
_ctx = ssl.create_default_context()
_REQUIRED = ("FR_AI_KEY", "FR_AI_BASE", "FR_AI_MODEL")

SYSTEM_PROMPT = (
    "你是财小白的金融科普助手,面向零基础新手。只做名词解释和概念科普,"
    "可以讲清策略概念(如什么是定投),但绝不推荐具体股票/基金标的,"
    "绝不预测涨跌,绝不给买卖建议。回答简短白话,不超过150字。"
)


def load_cfg():
    cfg = {}
    with open(SECRET, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    missing = [k for k in _REQUIRED if not cfg.get(k)]
    if missing:
        raise RuntimeError(f"ai.env 缺少必填项: {missing}")
    return cfg


def ask(question, cfg):
    body = json.dumps({
        "model": cfg["FR_AI_MODEL"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "max_tokens": 400,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        cfg["FR_AI_BASE"] + "/v1/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer " + cfg["FR_AI_KEY"],
            "Content-Type": "application/json",
        },
    )
    r = urllib.request.urlopen(req, timeout=20, context=_ctx)
    d = json.loads(r.read().decode("utf-8", "replace"))
    return d["choices"][0]["message"]["content"].strip()
