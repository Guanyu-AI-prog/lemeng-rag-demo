"""读智谱 429 的响应体,确认错误码含义"""
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

key = env.get("GLM_API_KEY", "")
for base in ["https://open.bigmodel.cn/api/coding/paas/v4", "https://open.bigmodel.cn/api/paas/v4"]:
    req = urllib.request.Request(
        base + "/embeddings",
        data=json.dumps({"model": "embedding-3", "input": ["test"], "dimensions": 512}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(base, "->", r.read().decode()[:200])
    except urllib.error.HTTPError as e:
        print(base, "->", e.code, "|", e.read().decode()[:300])
    except Exception as e:
        print(base, "->", repr(e)[:200])
