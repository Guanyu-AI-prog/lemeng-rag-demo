"""冒烟测试:验证新索引(bge-large API)下端到端问答"""
import json
import sys
import urllib.request

question = sys.argv[1] if len(sys.argv) > 1 else "GESP一年可以考几次?"
mode = sys.argv[2] if len(sys.argv) > 2 else "auto"

req = urllib.request.Request(
    "http://localhost:8001/ask",
    data=json.dumps({"question": question, "mode": mode}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=180) as r:
    d = json.load(r)

print("路由:", d["route"], "| 耗时:", d["elapsed"], "s | 缓存:", d.get("cached"), "| 答案字数:", len(d["answer"]))
