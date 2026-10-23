"""自动分流 + complex 路径验证"""
import json
import sys
import urllib.request

BASE = "http://localhost:8001"


def ask(question, mode="auto"):
    req = urllib.request.Request(
        f"{BASE}/ask",
        data=json.dumps({"question": question, "mode": mode}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp)


print("== 自动分流测试 ==")
for q in [
    "星芽有哪些课程?",                        # → faq
    "家长担心孩子坚持不下来,怎么回复?",        # → talk
    "帮我写一条机器人课的抖音脚本",            # → script
]:
    d = ask(q)
    print(f"  {d['route']:8s} ← {q}  ({d['elapsed']}s)")

print("\n== complex 路径 ==")
d = ask("孩子二年级学Scratch,之后想走信息学竞赛,应该怎么规划?")
print(f"路由: {d['route']} | 耗时: {d['elapsed']}s")
print("来源:", [s["title"] for s in d["sources"]])
print(d["answer"][:600])
