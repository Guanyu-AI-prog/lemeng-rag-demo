"""验证 SiliconFlow key:embedding + rerank 实际调用"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.embedder import Embedder
from retrieval.reranker import Reranker

e = Embedder()
v = e.embed_query("课程价格")
print("EMBED-OK | dim =", len(v))

r = Reranker()
hits = r.rerank("课程怎么收费", [
    {"text": "星芽课包制收费,档位5680/7980/23800元", "metadata": {}},
    {"text": "星芽在花都设有两个校区,均为社区点模式", "metadata": {}},
])
print("RERANK-OK | backend =", r.backend)
print("top1:", hits[0]["text"][:25], "| score =", round(hits[0]["rerank_score"], 4))
