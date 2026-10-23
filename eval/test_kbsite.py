"""测试 kb-site server.py(8866) → RAG(8001) 链路 + fallback"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8866"

print("== health ==")
with urllib.request.urlopen(f"{BASE}/health", timeout=30) as r:
    print(json.load(r))

print("\n== /ask(应走 RAG,来源带 /kb/ 链接)==")
req = urllib.request.Request(
    f"{BASE}/ask",
    data=json.dumps({"question": "星芽的课包是怎么收费的?"}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=120) as r:
    d = json.load(r)
print("answer 前120字:", d["answer"][:120].replace("\n", " "))
print("sources:")
for s in d["sources"]:
    print("  -", s["title"], "->", s["url"])

print("\n== /ask talk 类(应走 RAG 分流的话术路径)==")
req = urllib.request.Request(
    f"{BASE}/ask",
    data=json.dumps({"question": "家长说价格太贵,我该怎么回复家长?"}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=180) as r:
    d = json.load(r)
print("answer 前120字:", d["answer"][:120].replace("\n", " "))
print("sources 数量:", len(d["sources"]))
