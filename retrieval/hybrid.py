"""混合检索:多路查询(原查询+HyDE)→ 加权 RRF 融合 → Rerank → 邻接扩展 → top_k

对应两类检索优化(P0):
- HyDE 弥合"问法与文档措辞不同"的语义 gap(如"收费吗" vs "公益")
- 邻接扩展实现"检索小块、返回大块"(命中片段附带同文档上下文)
"""
import logging
from typing import List, Optional

from config import Config
from retrieval.bm25 import BM25Index
from retrieval.query_expansion import hyde_answer
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(self, vector_store: VectorStore, bm25: BM25Index, reranker: Reranker):
        self.vs = vector_store
        self.bm25 = bm25
        self.reranker = reranker

    def _single_query_hits(self, query: str, category: Optional[str]):
        """单路:向量 + BM25 原始命中列表"""
        v_hits = self.vs.search(query, top_k=Config.VECTOR_TOP_K, category=category)
        b_hits = self.bm25.search(query, top_k=Config.BM25_TOP_K)
        return v_hits, b_hits

    def _rrf_add(self, rrf: dict, by_key: dict, ranked: List[dict], weight: float = 1.0):
        for rank, h in enumerate(ranked):
            key = h["text"]
            rrf[key] = rrf.get(key, 0.0) + weight / (Config.RRF_K + rank + 1)
            by_key.setdefault(key, h)

    def _expand_neighbors(self, hits: List[dict]) -> List[dict]:
        """命中 chunk 附带同文档相邻 chunk(检索小块、返回大块)"""
        out = []
        for h in hits:
            meta = h.get("metadata", {})
            src, idx = meta.get("source"), meta.get("chunk_index")
            neighbors = self.vs.get_neighbors(src, idx) if (src is not None and idx is not None) else []
            if neighbors:
                extra = "\n".join(n["text"] for n in neighbors)[: Config.NEIGHBOR_CHARS]
                h = {**h, "text": f"{h['text']}\n[邻接上下文] {extra}"}
            out.append(h)
        return out

    def retrieve(self, query: str, top_k: int = 5, category: Optional[str] = None,
                 hyde: Optional[bool] = None, expand: Optional[bool] = None) -> List[dict]:
        """hyde/expand 默认取 Config 开关;评测时可显式传参对比"""
        hyde_on = Config.HYDE_ENABLED if hyde is None else hyde
        expand_on = Config.NEIGHBOR_EXPAND if expand is None else expand

        queries = [(query, 1.0)]
        if hyde_on:
            h = hyde_answer(query)
            if h:
                queries.append((h, Config.HYDE_WEIGHT))

        rrf: dict[str, float] = {}
        by_key: dict[str, dict] = {}
        n_calls = 0
        for q, weight in queries:
            v_hits, b_hits = self._single_query_hits(q, category)
            n_calls += 1
            self._rrf_add(rrf, by_key, v_hits, weight)
            self._rrf_add(rrf, by_key, b_hits, weight)

        fused = sorted(by_key.values(), key=lambda h: rrf[h["text"]], reverse=True)
        logger.info("检索: %d路×(向量%d+BM25%d) → 融合%d → rerank(%s)%s",
                    len(queries), Config.VECTOR_TOP_K, Config.BM25_TOP_K, len(fused),
                    self.reranker.backend, " +邻接扩展" if expand_on else "")
        ranked = self.reranker.rerank(query, fused, top_n=top_k)
        return self._expand_neighbors(ranked) if expand_on else ranked
