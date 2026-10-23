"""测试火山方舟 key 是否可调 embedding/rerank(plan key 大概率不行,验证一下)"""
import json
import urllib.error
import urllib.request
from pathlib import Path

env = {}
for line in (Path.home() / ".hermes" / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'\"")

key = env.get("ARK_API_KEY", "")
base = "https://ark.cn-beijing.volces.com/api/v3"
print("ARK KEY:", key[:8] + "***")


def post(path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()[:260]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:260]


print("embeddings:", post("/embeddings", {"model": "doubao-embedding-large-text-250515", "input": ["测试"]}))
print("rerank:    ", post("/rerank", {"model": "doubao-reranker-large-250515", "query": "测试", "documents": ["a", "b"]}))
