"""端到端测试:faq / talk / script 三条路径"""
import json
import sys
import urllib.request

BASE = "http://localhost:8001"

CASES = [
    ("faq", "星芽的课包是怎么收费的?"),
    ("talk", "家长觉得编程课太贵了,觉得不如报英语数学,我该怎么回复家长?"),
    ("script", "做一条面向花都家长的少儿编程试听课招生短视频脚本"),
]


def ask(question, mode):
    req = urllib.request.Request(
        f"{BASE}/ask",
        data=json.dumps({"question": question, "mode": mode}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.load(resp)


for mode, question in CASES:
    print("=" * 78)
    print(f"【{mode}】{question}")
    d = ask(question, mode)
    print(f"路由: {d['route']} | 耗时: {d['elapsed']}s | 来源: {[s['title'] for s in d['sources']]}")
    print("-" * 78)
    print(d["answer"][:800])
    print()
