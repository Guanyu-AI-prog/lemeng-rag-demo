"""验证 fallback:RAG 停机时 server.py 自动回退内置检索"""
import json
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8866/ask",
    data=json.dumps({"question": "星芽有哪些课程?"}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=120) as r:
    d = json.load(r)
print("answer 前100字:", d["answer"][:100].replace("\n", " "))
print("sources:", [(s["title"], s["url"][:40]) for s in d["sources"][:2]])
