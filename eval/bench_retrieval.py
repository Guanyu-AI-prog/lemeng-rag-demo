#!/usr/bin/env python3
"""诊断:单题检索各环节耗时(embedding/bm25/rerank/邻接)"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from retrieval.bm25 import BM25Index
from retrieval.embedder import Embedder
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore

q = "星芽的课程是怎么收费的"

e = Embedder()
store = VectorStore(e)

t0 = time.time()
v1 = store.search(q, top_k=20)
t_vec = time.time() - t0

t0 = time.time()
v2 = store.search(q, top_k=20)
t_vec2 = time.time() - t0

bm = BM25Index(store.all_records())
t_bm25_build = time.time() - t0 - t_vec2

t0 = time.time()
b = bm.search(q, top_k=10)
t_bm25 = time.time() - t0

r = Reranker()
t0 = time.time()
r.rerank(q, v1[:20])
t_rerank = time.time() - t0

t0 = time.time()
n = store.get_neighbors(v1[0]["metadata"].get("source"), v1[0]["metadata"].get("chunk_index"))
t_nb = time.time() - t0

print(f"向量检索(首查,含query embed): {t_vec:.2f}s")
print(f"向量检索(二查):               {t_vec2:.2f}s")
print(f"BM25 构建:                     {t_bm25_build:.2f}s")
print(f"BM25 查询:                     {t_bm25:.2f}s")
print(f"Rerank({r.backend}):           {t_rerank:.2f}s")
print(f"邻接查询:                      {t_nb:.2f}s")
print(f"单题合计(向量+bm25+rerank):   {t_vec + t_bm25 + t_rerank:.2f}s")
