"""看多轮改写到底把 query 改成了什么,以及改写后的 query 检索出什么"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.agent import LemengAgent
from retrieval.bm25 import BM25Index
from retrieval.embedder import Embedder
from retrieval.hybrid import HybridRetriever
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore

Q = "团队介绍里的老师"
TEAM = "团队.md"
HUADU = ("花都升学规划IP执行手册", "花都本地升学规划专家")

HIST_IP = [
    {"role": "user", "content": "帮我看看星芽的IP打造方案"},
    {"role": "assistant",
     "content": "星芽IP打造围绕创始人IP与升学规划人设展开，对外展示时需注意合规：背书真实可查、禁用命题专家等违规表述……（来源: 花都升学规划IP执行手册（终极全案）(1)）"},
    {"role": "user", "content": "对外展示的合规要求有哪些"},
    {"role": "assistant",
     "content": "合规要求主要有：1)背书真实可查，不虚构资质；2)禁用命题专家、考试院内部、官方合作等违规用语。（来源: 花都本地升学规划专家｜个人IP打造与四阶段获客全案）"},
]


def tags(docs):
    out = []
    for d in docs:
        s = str(d["metadata"].get("source", "")).split("/")[-1]
        mark = " ✔团队" if TEAM in s else (" ✘花都" if any(h in s for h in HUADU) else "")
        out.append(f"{s}#{d['metadata'].get('chunk_index')}{mark}")
    return out


def main():
    emb = Embedder()
    store = VectorStore(emb)
    agent = LemengAgent(HybridRetriever(store, BM25Index(store.all_records()), Reranker()))

    rw = agent._rewrite_query(Q, HIST_IP)
    print(f"IP合规历史 → 改写query: {rw!r}")
    docs = agent.retriever.retrieve(rw, top_k=5, hyde=True, expand=True)
    for t in tags(docs):
        print(f"    - {t}")

    # 双路对照:改写query与原query一起检索
    print("\n── 若改成『改写query+原query双路检索』:")
    seen, merged = set(), []
    for q in (rw, Q):
        for d in agent.retriever.retrieve(q, top_k=5, hyde=False):
            if d["text"] not in seen:
                seen.add(d["text"])
                merged.append(d)
    for t in tags(merged[:10]):
        print(f"    - {t}")


if __name__ == "__main__":
    main()
