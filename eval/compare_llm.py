"""对比测试:deepseek-chat vs 智谱 flash(Coding Plan key)在同一话术任务上的表现"""
import json
import sys
import time
import urllib.request
from pathlib import Path

env = {}
for line in (Path.home() / ".hermes" / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'\"")

DEEPSEEK = {
    "base": env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
    "key": env.get("DEEPSEEK_API_KEY", ""),
}
GLM = {
    "base": env.get("GLM_BASE_URL", "").rstrip("/"),
    "key": env.get("GLM_API_KEY", ""),
}

PROMPT = """你是「星芽少儿编程」的资深销售培训师。家长说:"编程课太贵了,不如报英语数学实际"。
请给出:1.场景分析一两句 2.一句开场话术 3.核心话术(150字内) 4.一句促成动作。
语气真诚不油腻,不承诺升学结果。"""


def call(base, key, model, timeout=120):
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0.3,
            "max_tokens": 2000,
        }).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    elapsed = time.time() - t0
    msg = d["choices"][0]["message"]
    usage = d.get("usage", {})
    detail = usage.get("completion_tokens_details") or {}
    return {
        "model": model,
        "ok": True,
        "elapsed": round(elapsed, 1),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": detail.get("reasoning_tokens"),
        "content_len": len(msg.get("content") or ""),
        "content": (msg.get("content") or "")[:220],
        "finish": d["choices"][0].get("finish_reason"),
    }


cases = [
    (DEEPSEEK["base"], DEEPSEEK["key"], "deepseek-chat"),
    (GLM["base"], GLM["key"], "glm-4.7-flash"),
    (GLM["base"], GLM["key"], "glm-5.3-flash"),
]
for base, key, model in cases:
    if not key:
        print(f"== {model}: 无 key,跳过 ==")
        continue
    print(f"== {model} ==")
    try:
        r = call(base, key, model)
        for k, v in r.items():
            if k != "content":
                print(f"  {k}: {v}")
        print(f"  content预览: {r['content'][:150]}...")
    except Exception as e:
        print(f"  失败: {str(e)[:180]}")
    print()
