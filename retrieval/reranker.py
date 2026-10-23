"""Rerank:local(CrossEncoder)/ api(SiliconFlow)/ off 三后端,失败自动降级"""
import logging
import os
from typing import List

from config import Config

logger = logging.getLogger(__name__)
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


class Reranker:
    def __init__(self):
        self.backend = Config.RERANK_BACKEND
        self._model = None
        if self.backend == "local":
            try:
                from sentence_transformers import CrossEncoder
                logger.info("加载本地 rerank 模型 %s ...", Config.RERANK_MODEL)
                self._model = CrossEncoder(Config.RERANK_MODEL, max_length=512)
            except Exception as e:
                logger.warning("本地 rerank 加载失败,降级为 off: %s", e)
                self.backend = "off"
        elif self.backend in ("api", "zhipu"):
            key = Config.SILICONFLOW_API_KEY if self.backend == "api" else Config.ZHIPU_API_KEY
            if not key:
                logger.warning("RERANK_BACKEND=%s 但未配置 key,降级为 off", self.backend)
                self.backend = "off"

    @property
    def available(self) -> bool:
        return self.backend in ("local", "api", "zhipu")

    def rerank(self, query: str, hits: List[dict], top_n: int = None) -> List[dict]:
        """hits: [{text, metadata, ...}],返回按相关性重排的前 top_n 条,附加 rerank_score"""
        top_n = top_n or Config.RERANK_TOP_N
        if not hits:
            return []
        if not self.available or len(hits) <= 1:
            return hits[:top_n]

        try:
            if self.backend == "local":
                pairs = [(query, h["text"][:1500]) for h in hits]
                scores = self._model.predict(pairs)
                for h, s in zip(hits, scores):
                    h["rerank_score"] = float(s)
            elif self.backend == "zhipu":
                scores = self._rerank_zhipu(query, hits)
                for h, s in zip(hits, scores):
                    h["rerank_score"] = float(s)
            else:
                scores = self._rerank_api(query, hits)
                for h, s in zip(hits, scores):
                    h["rerank_score"] = float(s)
            hits.sort(key=lambda h: h["rerank_score"], reverse=True)
            return hits[:top_n]
        except Exception as e:
            logger.warning("rerank 失败,按原序返回: %s", e)
            return hits[:top_n]

    def _rerank_zhipu(self, query: str, hits: List[dict]) -> List[float]:
        """智谱 rerank:POST /rerank,响应按 index 对齐回原顺序"""
        import requests
        resp = requests.post(
            f"{Config.ZHIPU_API_BASE}/rerank",
            headers={"Authorization": f"Bearer {Config.ZHIPU_API_KEY}"},
            json={
                "model": "rerank",
                "query": query[:4096],
                "documents": [h["text"][:4096] for h in hits],
                "top_n": len(hits),
            },
            timeout=30,
        )
        resp.raise_for_status()
        results = sorted(resp.json()["results"], key=lambda r: r["index"])
        return [r["relevance_score"] for r in results]

    def _rerank_api(self, query: str, hits: List[dict]) -> List[float]:
        import requests
        resp = requests.post(
            f"{Config.SILICONFLOW_API_BASE}/rerank",
            headers={"Authorization": f"Bearer {Config.SILICONFLOW_API_KEY}"},
            json={
                "model": Config.RERANK_MODEL,
                "query": query,
                "documents": [h["text"][:1500] for h in hits],
                "return_documents": False,
            },
            timeout=30,
        )
        resp.raise_for_status()
        results = sorted(resp.json()["results"], key=lambda r: r["index"])
        return [r["relevance_score"] for r in results]
