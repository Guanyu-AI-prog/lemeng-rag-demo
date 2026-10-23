"""检索层对比评测:用 eval_kb30 的 30 题,对比新旧检索的 top2 命中率

旧方案(lemeng_web 关键词打分)基线:26/30 = 86.7%(eval_report_kb30.md, 2026-08-08)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from sample_questions import KB30_QUESTIONS
from retrieval.bm25 import BM25Index
from retrieval.embedder import Embedder
from retrieval.hybrid import HybridRetriever
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore


def main():
    embedder = Embedder()
    store = VectorStore(embedder)
    retriever = HybridRetriever(store, BM25Index(store.all_records()), Reranker())

    hit_count = 0
    misses = []
    for q in KB30_QUESTIONS:
        docs = retriever.retrieve(q["question"], top_k=2)
        # 归一化:知识库文档标题存在空格差异(如 "AI 辅助写作规则" vs "AI辅助写作规则")
        norm = lambda s: s.replace(" ", "").replace("\u3000", "")
        titles = [norm(d.get("metadata", {}).get("title", "")) for d in docs]
        hit = any(any(norm(exp) in t for t in titles) for exp in q["expected_docs"])
        hit_count += hit
        mark = "✅" if hit else "❌"
        print(f"{mark} {q['id']} [{q['folder']}] {q['question'][:30]}")
        if not hit:
            misses.append(q["id"])
            print(f"      期望: {q['expected_docs']} | 实际: {titles}")

    print("=" * 60)
    print(f"检索 top2 命中: {hit_count}/30 = {hit_count/30:.1%}")
    print(f"旧方案基线:    26/30 = 86.7%")
    print(f"未命中: {misses if misses else '无'}")


if __name__ == "__main__":
    main()
