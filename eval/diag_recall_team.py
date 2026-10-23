"""诊断:「团队介绍里的老师」为何召不回 团队.md(只检索,不生成,不加 HyDE)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.bm25 import tokenize
from retrieval.embedder import Embedder
from retrieval.vector_store import VectorStore

QUERIES = [
    "团队介绍里的老师",   # 用户反馈:召不回
    "星芽的教师有哪些",   # 对照:能召回
    "团队介绍",           # 极简问法
    "老师有哪些",         # 去掉"团队介绍"
]
TEAM_KEY = "团队"  # data/🏢企业基础/团队.md,chunk source 含此文件名


def short(h):
    m = h["metadata"]
    return f"{str(m.get('source', '?')).split('/')[-1]}#{m.get('chunk_index')}"


def main():
    emb = Embedder()
    store = VectorStore(emb)
    records = store.all_records()
    print(f"索引共 {len(records)} 条")
    team = [(i, r) for i, r in enumerate(records) if TEAM_KEY in str(r["metadata"].get("source", ""))]
    print(f"团队.md 相关 chunk {len(team)} 条:")
    for i, r in team:
        sec = r["metadata"].get("section", "")
        print(f"  [{i}] {sec} | {r['text'][:70]!r}")

    for q in QUERIES:
        print("=" * 78)
        print(f"Q: {q}   jieba: {tokenize(q)}")
        v_hits = store.search(q, top_k=20)
        print("  向量 top10:")
        for h in v_hits[:10]:
            print(f"    d={h['distance']:.3f} {short(h)} | {h['text'][:55]!r}")
        tv = [(j + 1, h["distance"]) for j, h in enumerate(v_hits) if TEAM_KEY in str(h["metadata"].get("source", ""))]
        print(f"  >> 团队.md 在向量 top20: {[(r, round(d, 3)) for r, d in tv] or '未命中'}")
        from retrieval.bm25 import BM25Index
        b_hits = BM25Index(records).search(q, top_k=10)
        print("  BM25 top10:")
        for h in b_hits:
            print(f"    s={h['bm25_score']:.2f} {short(h)} | {h['text'][:55]!r}")
        tb = [(j + 1, round(h["bm25_score"], 2)) for j, h in enumerate(b_hits)
              if TEAM_KEY in str(h["metadata"].get("source", ""))]
        print(f"  >> 团队.md 在 BM25 top10: {tb or '未命中'}")


if __name__ == "__main__":
    main()
