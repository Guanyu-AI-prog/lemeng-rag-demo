"""从 ~/.hermes/.env 提取 DeepSeek 配置生成本项目 .env(一次性工具)"""
from pathlib import Path

home = Path.home()
src = {}
for line in (home / ".hermes" / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        src[k.strip()] = v.strip().strip("'\"")

env = f"""LLM_API_KEY={src.get("DEEPSEEK_API_KEY", "")}
LLM_API_BASE={src.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")}
LLM_MODEL=deepseek-v4-flash
EMBED_BACKEND=local
EMBED_MODEL=BAAI/bge-small-zh-v1.5
EMBED_DIM=512
RERANK_BACKEND=local
RERANK_MODEL=BAAI/bge-reranker-base
API_HOST=0.0.0.0
API_PORT=8001
"""

out = Path(__file__).resolve().parent / ".env"
out.write_text(env)
print("生成 .env:", out)
print("LLM_API_BASE =", src.get("DEEPSEEK_BASE_URL", "(默认)"))
print("LLM_API_KEY =", (src.get("DEEPSEEK_API_KEY", "") or "")[:8] + "***")
