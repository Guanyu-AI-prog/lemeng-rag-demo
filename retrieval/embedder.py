"""Embedding 封装:local(sentence-transformers)/ api(SiliconFlow)双后端"""
import logging
import os
from typing import List

from config import Config

logger = logging.getLogger(__name__)

# HF 直连不稳,默认走国内镜像
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


class Embedder:
    def __init__(self):
        self.backend = Config.EMBED_BACKEND
        self.model = Config.EMBED_MODEL
        if self.backend == "local":
            from sentence_transformers import SentenceTransformer
            logger.info("加载本地 embedding 模型 %s ...", self.model)
            self._st = SentenceTransformer(self.model)
            self.dim = self._st.get_sentence_embedding_dimension()
        elif self.backend == "api":
            from openai import OpenAI
            if not Config.SILICONFLOW_API_KEY:
                raise ValueError("EMBED_BACKEND=api 需要设置 SILICONFLOW_API_KEY")
            self._client = OpenAI(
                api_key=Config.SILICONFLOW_API_KEY,
                base_url=Config.SILICONFLOW_API_BASE,
                timeout=45,
                max_retries=3,
            )
            self.dim = Config.EMBED_DIM
        elif self.backend == "zhipu":
            if not Config.ZHIPU_API_KEY:
                raise ValueError("EMBED_BACKEND=zhipu 需要设置 ZHIPU_API_KEY")
            self.model = Config.ZHIPU_EMBED_MODEL
            self.dim = Config.EMBED_DIM  # embedding-3 通过 dimensions 参数对齐
        else:
            raise ValueError(f"未知 EMBED_BACKEND: {self.backend}")
        logger.info("Embedding 就绪 backend=%s model=%s dim=%s", self.backend, self.model, self.dim)

    def _encode_zhipu(self, texts: List[str], is_query: bool) -> List[List[float]]:
        """智谱 embedding-3:POST /embeddings,最多 64 条/批,dimensions 可调"""
        import requests
        out: List[List[float]] = []
        batch = 64
        for i in range(0, len(texts), batch):
            resp = requests.post(
                f"{Config.ZHIPU_API_BASE}/embeddings",
                headers={"Authorization": f"Bearer {Config.ZHIPU_API_KEY}"},
                json={"model": self.model, "input": texts[i: i + batch],
                      "dimensions": self.dim},
                timeout=60,
            )
            resp.raise_for_status()
            data = sorted(resp.json()["data"], key=lambda x: x["index"])
            out.extend([d["embedding"] for d in data])
        return out

    def _encode_local(self, texts: List[str], is_query: bool) -> List[List[float]]:
        if is_query:
            texts = [Config.BGE_QUERY_INSTRUCTION + t for t in texts]
        vecs = self._st.encode(
            texts, batch_size=64, normalize_embeddings=True, show_progress_bar=len(texts) > 128
        )
        return [v.tolist() for v in vecs]

    def _encode_api(self, texts: List[str], is_query: bool) -> List[List[float]]:
        if is_query:
            texts = [Config.BGE_QUERY_INSTRUCTION + t for t in texts]
        # bge 系列输入上限 512 token,超长 chunk(含标题前缀)需截断
        texts = [t[:500] if len(t) > 500 else t for t in texts]
        out: List[List[float]] = []
        batch = 32
        for i in range(0, len(texts), batch):
            resp = self._client.embeddings.create(model=self.model, input=texts[i: i + batch])
            data = sorted(resp.data, key=lambda x: x.index)
            out.extend([d.embedding for d in data])
        return out

    def encode(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        if not texts:
            return []
        if self.backend == "local":
            return self._encode_local(texts, is_query)
        if self.backend == "zhipu":
            return self._encode_zhipu(texts, is_query)
        return self._encode_api(texts, is_query)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.encode(texts, is_query=False)

    def embed_query(self, text: str) -> List[float]:
        return self.encode([text], is_query=True)[0]
