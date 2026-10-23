"""复现矩阵:A=HyDE方差(3次独立检索) B=多轮history改写带偏场景"""
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


def tags(docs):
    srcs = [str(d["metadata"].get("source", "")).split("/")[-1] for d in docs]
    t = []
    for d, s in zip(docs, srcs):
        mark = ""
        if TEAM in s:
            mark = " ✔团队"
        elif any(h in s for h in HUADU):
            mark = " ✘花都"
        t.append(f"{s}#{d['metadata'].get('chunk_index')}{mark}")
    return t


def main():
    emb = Embedder()
    store = VectorStore(emb)
    agent = LemengAgent(HybridRetriever(store, BM25Index(store.all_records()), Reranker()))

    print("=== A. HyDE 方差:同一问法独立检索 3 次 ===")
    for i in range(3):
        docs = agent.retriever.retrieve(Q, top_k=5, hyde=True, expand=True)
        hit = any(TEAM in str(d["metadata"].get("source", "")) for d in docs)
        print(f"  第{i + 1}轮 团队.md命中={hit}")
        for t in tags(docs):
            print(f"    - {t}")

    print("\n=== B. 多轮 history 改写场景(前文在聊对外展示/IP合规) ===")
    history = [
        {"role": "user", "content": "帮我看看星芽的IP打造方案"},
        {"role": "assistant",
         "content": "星芽IP打造围绕创始人IP与升学规划人设展开，对外展示时需注意合规：背书真实可查、禁用命题专家等违规表述……（来源: 花都升学规划IP执行手册（终极全案）(1)）"},
        {"role": "user", "content": "对外展示的合规要求有哪些"},
        {"role": "assistant",
         "content": "合规要求主要有：1)背书真实可查，不虚构资质；2)禁用命题专家、考试院内部、官方合作等违规用语；3)可替换为'基于官方公开政策解读、多年行业经验总结'。（来源: 花都本地升学规划专家｜个人IP打造与四阶段获客全案）"},
    ]
    messages, docs = agent._prepare("faq", Q, history)
    rewritten = messages[-1]["content"]
    import re
    m = re.search(r"【问题】\n(.+?)\n", rewritten) or re.search(r"问题[:：]?\s*(.+)", rewritten)
    print(f"  改写后 query ≈ {m.group(1) if m else '(见下)'}")
    print("  检索结果:")
    for t in tags(docs):
        print(f"    - {t}")
    print("\n=== B2. 单纯带历史但历史话题无关(聊课程价格) ===")
    hist2 = [
        {"role": "user", "content": "课程价格多少"},
        {"role": "assistant", "content": "正价课按 L2/L3 阶段收费……（来源: 课程价格）"},
    ]
    _, docs2 = agent._prepare("faq", Q, hist2)
    for t in tags(docs2):
        print(f"    - {t}")


if __name__ == "__main__":
    main()
