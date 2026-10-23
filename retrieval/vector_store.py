"""Chroma 向量库封装"""
import logging
from typing import List, Optional

import chromadb

from config import Config
from retrieval.embedder import Embedder

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, embedder: Embedder):
        self.embedder = embedder
        self.client = chromadb.PersistentClient(path=Config.VECTOR_DB_PATH)
        self.collection = self.client.get_or_create_collection(
            name=Config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("向量库就绪: %s (%d 条)", Config.COLLECTION_NAME, self.count())

    def count(self) -> int:
        return self.collection.count()

    def add(self, texts: List[str], embeddings: List[List[float]], metadatas: List[dict]):
        batch = 256
        for i in range(0, len(texts), batch):
            self.collection.add(
                ids=[f"c_{i + j}" for j in range(len(texts[i: i + batch]))],
                documents=texts[i: i + batch],
                embeddings=embeddings[i: i + batch],
                metadatas=metadatas[i: i + batch],
            )

    def search(self, query: str, top_k: int = 20, category: Optional[str] = None) -> List[dict]:
        """返回 [{text, metadata, distance}],按相似度升序(distance 越小越近)"""
        qvec = self.embedder.embed_query(query)
        where = {"category": category} if category else None
        res = self.collection.query(
            query_embeddings=[qvec],
            n_results=min(top_k, max(self.count(), 1)),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        if res["documents"] and res["documents"][0]:
            for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
                hits.append({"text": doc, "metadata": meta or {}, "distance": dist})
        return hits

    def get_neighbors(self, source: str, chunk_index: int, offsets=(-1, 1)) -> List[dict]:
        """取同文档相邻 chunk(按 chunk_index),返回按 index 升序的 [{text, metadata}]"""
        if source is None or chunk_index is None:
            return []
        want = [chunk_index + o for o in offsets if chunk_index + o >= 0]
        if not want:
            return []
        try:
            res = self.collection.get(
                where={"$and": [{"source": source}, {"chunk_index": {"$in": want}}]},
                include=["documents", "metadatas"],
            )
        except Exception:
            return []
        items = [
            {"text": doc, "metadata": meta or {}, "chunk_index": (meta or {}).get("chunk_index", 0)}
            for doc, meta in zip(res["documents"], res["metadatas"])
        ]
        items.sort(key=lambda x: x["chunk_index"])
        return items

    def all_records(self) -> List[dict]:
        """取全部文档(用于构建 BM25 索引): [{id, text, metadata}]"""
        if self.count() == 0:
            return []
        data = self.collection.get(include=["documents", "metadatas"])
        return [
            {"id": cid, "text": doc, "metadata": meta or {}}
            for cid, doc, meta in zip(data["ids"], data["documents"], data["metadatas"])
        ]
