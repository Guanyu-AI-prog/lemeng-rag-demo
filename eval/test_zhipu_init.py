"""验证 zhipu 后端代码可正常初始化(不实际调 API)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

config.Config.EMBED_BACKEND = "zhipu"
config.Config.RERANK_BACKEND = "zhipu"
config.Config.ZHIPU_API_KEY = "dummy-for-init-test"

from retrieval.embedder import Embedder
from retrieval.reranker import Reranker

e = Embedder()
print("Embedder zhipu 初始化 OK | model =", e.model, "| dim =", e.dim)
r = Reranker()
print("Reranker zhipu 初始化 OK | backend =", r.backend, "| available =", r.available)
