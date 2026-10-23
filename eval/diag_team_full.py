"""复现生产 faq 检索全链路:改写(恒等)→HyDE→RRF→Rerank,逐层看『团队介绍里的老师』排到哪"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from retrieval.bm25 import BM25Index
from retrieval.embedder import Embedder
from retrieval.hybrid import HybridRetriever
from retrieval.query_expansion import hyde_answer
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore

Q = "团队介绍里的老师"
TEAM_KEY = "团队"


def short(h):
    m = h["metadata"]
    return f"{str(m.get('source', '?')).split('/')[-1]}#{m.get('chunk_index')}"


def main():
    emb = Embedder()
    store = VectorStore(emb)
    records = store.all_records()
    retriever = HybridRetriever(store, BM25Index(records), Reranker())

    # 第1层:HyDE 生成内容
    h = hyde_answer(Q)
    print("=== HyDE 假设片段 ===")
    print(h)

    # 第2层:两路各自命中(原查询 + HyDE)
    print("\n=== 原查询 两路 top10 ===")
    v1 = store.search(Q, top_k=Config.VECTOR_TOP_K)
    b1 = retriever.bm25.search(Q, top_k=Config.BM25_TOP_K)
    for label, hits in (("V", v1), ("B", b1)):
        tops = ", ".join(f"{short(x)}" for x in hits[:10])
        print(f"  {label}: {tops}")
    print("=== HyDE 查询 两路 top10 ===")
    v2 = store.search(h, top_k=Config.VECTOR_TOP_K)
    b2 = retriever.bm25.search(h, top_k=Config.BM25_TOP_K)
    for label, hits in (("V", v2), ("B", b2)):
        tops = ", ".join(f"{short(x)}" for x in hits[:10])
        print(f"  {label}: {tops}")

    # 第3层:RRF 融合明细
    rrf, by_key = {}, {}
    for q, w in ((Q, 1.0), (h, Config.HYDE_WEIGHT)):
        for hits in (store.search(q, top_k=Config.VECTOR_TOP_K), retriever.bm25.search(q, top_k=Config.BM25_TOP_K)):
            for rank, hh in enumerate(hits):
                rrf[hh["text"]] = rrf.get(hh["text"], 0.0) + w / (Config.RRF_K + rank + 1)
                by_key.setdefault(hh["text"], hh)
    fused = sorted(by_key.values(), key=lambda x: rrf[x["text"]], reverse=True)
    print("\n=== RRF 融合 top15 ===")
    for i, x in enumerate(fused[:15]):
        print(f"  {i + 1}. rrf={rrf[x['text']]:.5f} {short(x)} | {x['text'][:40]!r}")
    trrf = [(i + 1, round(rrf[x["text"]], 5)) for i, x in enumerate(fused) if TEAM_KEY in str(x["metadata"].get("source", ""))]
    print(f"  >> 团队.md 在融合榜: {trrf[:8] or '未命中'}")

    # 第4层:Rerank 之后的生产 top5
    final = retriever.retrieve(Q, top_k=5, hyde=True, expand=True)
    print("\n=== 生产最终 top5(含邻接扩展) ===")
    for i, x in enumerate(final):
        team = " <== 团队.md" if TEAM_KEY in str(x["metadata"].get("source", "")) else ""
        print(f"  {i + 1}. {short(x)}{team}")
        print(f"     {x['text'][:100]!r}")


if __name__ == "__main__":
    main()
