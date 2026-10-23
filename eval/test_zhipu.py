"""验证智谱 embedding / rerank API 可用性(key 从 ~/.hermes/.env 读取)"""
import json
import sys
import urllib.request
from pathlib import Path

env = {}
for line in (Path.home() / ".hermes" / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'\"")

KEY = env.get("GLM_API_KEY", "")
# 依次尝试:coding plan 端点(hermes 配置)与开放平台通用端点
CANDIDATES = [
    env.get("GLM_BASE_URL", "").rstrip("/"),
    "https://open.bigmodel.cn/api/paas/v4",
]
print(f"KEY = {KEY[:8]}***")


def post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


for base in CANDIDATES:
    if not base:
        continue
    print(f"\n== 尝试端点 {base} ==")
    try:
        r = post(base, "/embeddings", {"model": "embedding-3", "input": ["星芽少儿编程怎么样", "课程价格多少"], "dimensions": 512})
        print("embedding-3 OK | 条数:", len(r["data"]), "| 维度:", len(r["data"][0]["embedding"]), "| tokens:", r.get("usage"))
        BASE = base
        break
    except Exception as e:
        print("失败:", str(e)[:160])
else:
    sys.exit("两个端点都不可用")

print("\n== rerank ==")
r = post(BASE, "/rerank", {
    "model": "rerank",
    "query": "课程怎么收费",
    "documents": [
        "星芽课包制收费,档位 5680/7980/23800/33800/63800 元",
        "星芽在花都设有两个校区,均为社区点模式",
        "试听课流程:破冰、体验、成果展示、家长沟通",
    ],
    "top_n": 3,
})
for item in r["results"]:
    print(f"  index={item['index']} score={item['relevance_score']:.4f}")
