"""复现 script 路径:真实检索上下文 + SCRIPT_PROMPT,看 finish_reason/usage"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from agent.prompts import CONSULTANT_SYSTEM, SCRIPT_PROMPT
from openai import OpenAI
from retrieval.bm25 import BM25Index
from retrieval.embedder import Embedder
from retrieval.hybrid import HybridRetriever
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore

topic = "做一条面向花都家长的少儿编程试听课招生短视频脚本"

embedder = Embedder()
store = VectorStore(embedder)
retriever = HybridRetriever(store, BM25Index(store.all_records()), Reranker())

docs = retriever.retrieve(topic, top_k=5) + retriever.retrieve("短视频选题 IP打造 获客", top_k=5, category="品牌输出")
context = "\n\n".join(f"{d['text']}" for d in docs)[:6000]
print(f"上下文长度: {len(context)}")

client = OpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_API_BASE, timeout=300)
resp = client.chat.completions.create(
    model=Config.LLM_MODEL,
    messages=[{"role": "user", "content": SCRIPT_PROMPT.format(context=context, topic=topic)}],
    temperature=0.3,
    max_tokens=4000,
)
msg = resp.choices[0]
print("finish_reason:", msg.finish_reason)
print("usage:", resp.usage)
print("content 长度:", len(msg.message.content or ""))
rc = getattr(msg.message, "reasoning_content", None) or ""
print("reasoning 长度:", len(rc))
print("content 前300:", (msg.message.content or "")[:300])
