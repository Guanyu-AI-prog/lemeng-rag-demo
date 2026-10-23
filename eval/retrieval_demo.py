"""检索层验证:用 eval_kb30 中因'表格/小节 chunk 未进 top2'而失分的典型问题测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from retrieval.bm25 import BM25Index
from retrieval.embedder import Embedder
from retrieval.hybrid import HybridRetriever
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore

# eval_kb30 失分/部分失分题 + 几个新场景(话术/脚本检索)
CASES = [
    ("课程怎么收费?有哪几个课包档位?", "课程价格表应进 top2(原 q04 失分)"),
    ("用AI写宣传文案,哪些词不能出现?", "禁用词小节应进 top2(原 q06 失分)"),
    ("5岁的孩子能学编程吗?", "FAQ 应命中(原 q10 失分)"),
    ("星芽在花都有哪两个校区?", "校区信息应进 top2(原 q03 失分)"),
    ("获客渠道有哪些?", "渠道矩阵表格应命中(原 q07 部分失分)"),
    ("Scratch 和 C++ 有什么区别?孩子该怎么选?", "多文档对比(complex 场景)"),
    ("家长问学编程有什么用,怎么回复?", "话术场景:应命中 FAQ/试听课话术"),
    ("做一条少儿编程招生的短视频脚本", "脚本场景:应命中品牌输出/课程卖点"),
]

def main():
    embedder = Embedder()
    store = VectorStore(embedder)
    bm25 = BM25Index(store.all_texts())
    retriever = HybridRetriever(store, bm25, Reranker())

    print(f"\n索引: {store.count()} chunks\n" + "=" * 78)
    for query, note in CASES:
        docs = retriever.retrieve(query, top_k=3)
        print(f"\n❓ {query}\n   ({note})")
        for i, d in enumerate(docs, 1):
            m = d["metadata"]
            score = d.get("rerank_score")
            score_s = f"{score:+.3f}" if score is not None else "-"
            print(f"   {i}. [{score_s}] {m.get('category')}/{m.get('title')} > {m.get('section', '')[:40]}")
            print(f"      {d['text'][:80].replace(chr(10), ' ')}...")

if __name__ == "__main__":
    main()
