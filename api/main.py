"""星芽知识库 RAG 服务

    POST /ask      统一问答入口(自动分流:faq/talk/script/complex,可用 mode 强制指定)
    POST /retrieve 纯检索(不生成,调试/供其他系统调用)
    GET  /health   健康检查 + 索引状态

启动: .venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8001
"""
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import Config
from agent.agent import LemengAgent
from agent.llm import get_client
from cache import faq_cache
from memory import session_memory
from retrieval.bm25 import BM25Index
from retrieval.embedder import Embedder
from retrieval.hybrid import HybridRetriever
from retrieval.reranker import Reranker
from retrieval.vector_store import VectorStore

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
logger = logging.getLogger("lemeng-rag")

app = FastAPI(title="星芽知识库 RAG", version="0.1.0")
_state = {}


@app.on_event("startup")
def startup():
    Config.validate()
    t0 = time.time()
    embedder = Embedder()
    store = VectorStore(embedder)
    if store.count() == 0:
        logger.warning("向量库为空!请先运行: python ingest/build_index.py --force")
    bm25 = BM25Index(store.all_records())
    retriever = HybridRetriever(store, bm25, Reranker())
    _state["agent"] = LemengAgent(retriever)
    _state["count"] = store.count()
    logger.info("启动完成 %.1fs,索引 %d 条", time.time() - t0, store.count())


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field("auto", description="auto/faq/talk/script/complex")
    session_id: Optional[str] = Field(None, description="会话 ID,服务端据此读取/保存历史")
    history: Optional[List[dict]] = Field(None, description="显式历史,优先级高于 session_id")


def _build_history(req: AskRequest) -> List[dict]:
    """构建本次调用的历史消息列表(只保留 role/content,过滤前端附加字段如 sources)。"""
    raw: List[dict] = []
    if req.history:
        raw = [h for h in req.history if h.get("role") in ("user", "assistant")]
    elif req.session_id:
        raw = session_memory.get(req.session_id)
    return [{"role": h["role"], "content": h.get("content", "")} for h in raw]


def _save_turn(req: AskRequest, answer: str):
    """把本轮 QA 保存到 session memory。"""
    if not req.session_id:
        return
    session_memory.append(req.session_id, "user", req.question)
    session_memory.append(req.session_id, "assistant", answer)


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = None
    top_k: int = Field(5, ge=1, le=20)


class Source(BaseModel):
    title: str = ""
    source: str = ""
    category: str = ""
    section: str = ""


class AskResponse(BaseModel):
    answer: str
    sources: List[Source] = []
    route: str
    elapsed: float
    cached: bool = False


def _as_source_dicts(labels: List[str]):
    """来源标签 "title(source)" 拆回结构化"""
    out = []
    for label in labels:
        title, _, src = label.partition("(")
        out.append({"title": title, "source": src.rstrip(")"),
                    "category": "", "section": ""})
    return out


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    t0 = time.time()
    history = _build_history(req)
    result = _state["agent"].handle(req.question, mode=req.mode, history=history)
    _save_turn(req, result["answer"])
    return AskResponse(
        answer=result["answer"],
        sources=[Source(**{k: s.get(k, "") for k in ("title", "source", "category", "section")})
                 for s in _as_source_dicts(result["sources"])],
        route=result["route"],
        elapsed=round(time.time() - t0, 2),
        cached=result.get("cached", False),
    )


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """SSE 流式:meta(路由+来源) → delta*(增量文本) → done(耗时/缓存标记)

    注意:meta 在检索完成后立即下发(talk/script 约 2-5s,faq 约 1-3s),正文随后逐字推送。
    """
    history = _build_history(req)

    def gen():
        parts = []
        for ev in _state["agent"].stream_answer(req.question, mode=req.mode, history=history):
            if ev["event"] == "delta":
                parts.append(ev["data"].get("text", ""))
            yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
        _save_turn(req, "".join(parts))

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/retrieve")
def retrieve(req: RetrieveRequest):
    docs = _state["agent"].retriever.retrieve(req.query, top_k=req.top_k,
                                              category=req.category)
    return {"results": [
        {"text": d["text"], "metadata": d.get("metadata", {}),
         "rerank_score": d.get("rerank_score")} for d in docs
    ]}


@app.get("/health")
def health():
    return {"status": "ok", "chunks": _state.get("count", 0),
            "llm_model": Config.LLM_MODEL,
            "faq_cache": faq_cache.stats(),
            "session_memory": session_memory.stats()}


@app.post("/session/clear")
def session_clear(session_id: str):
    session_memory.clear(session_id)
    return {"status": "ok", "session_id": session_id}
