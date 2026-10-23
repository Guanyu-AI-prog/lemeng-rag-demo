#!/usr/bin/env python3
"""计时:本地 embedding / rerank 模型加载各阶段耗时(用环境变量覆盖,不改 .env)"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["EMBED_BACKEND"] = "local"
os.environ["RERANK_BACKEND"] = "local"

import config
config.Config.EMBED_BACKEND = "local"
config.Config.RERANK_BACKEND = "local"

t0 = time.time()
from retrieval.embedder import Embedder
from retrieval.reranker import Reranker
t_import = time.time() - t0

t0 = time.time()
e = Embedder()
t_embed = time.time() - t0

t0 = time.time()
r = Reranker()
t_rerank = time.time() - t0

# 模拟一次实际推理,看首查延迟
t0 = time.time()
e.encode(["测试查询"], is_query=True)
t_embed_first = time.time() - t0

t0 = time.time()
r.rerank("测试", [{"text": "a", "metadata": {}}, {"text": "b", "metadata": {}}])
t_rerank_first = time.time() - t0

print(f"import 耗时:          {t_import:.1f}s")
print(f"Embedding 模型加载:   {t_embed:.1f}s  (bge-small-zh-v1.5)")
print(f"Rerank 模型加载:      {t_rerank:.1f}s  (bge-reranker-base)")
print(f"Embedding 首次推理:   {t_embed_first:.1f}s")
print(f"Rerank 首次推理:      {t_rerank_first:.1f}s")
print(f"合计(加载+首查):     {t_import + t_embed + t_rerank + t_embed_first + t_rerank_first:.1f}s")
