"""端到端:faq 路径真实生成,验证『团队介绍里的老师』当前答案质量"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.agent import LemengAgent
from retrieval.bm25 import BM25Index
from retrieval.embedder import Embedder
from retrieval.hybrid import HybridRetriever
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore


def main():
    emb = Embedder()
    store = VectorStore(emb)
    agent = LemengAgent(HybridRetriever(store, BM25Index(store.all_records()), Reranker()))
    for q in ["团队介绍里的老师", "星芽的教师有哪些"]:
        r = agent.answer_faq(q)
        print("=" * 78)
        print(f"Q: {q}  route={r['route']} cached={r.get('cached', False)}")
        print(r["answer"][:600])
        print("── sources:", r["sources"])


if __name__ == "__main__":
    main()
