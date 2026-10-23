"""星芽知识库 Agent

四条路径:
  faq     单跳事实问答 → 混合检索 → 课程顾问生成(带来源,TTL 缓存)
  talk    家长营销话术 → 检索(场景 + 话术/价格资料)→ 话术生成
  script  短视频拍摄脚本 → 检索(主题 + 品牌输出资料)→ 分镜脚本生成
  complex 复杂问题 → 工具循环(检索工具,最多 AGENT_MAX_ITERATIONS 轮)

handle() 返回完整结果;stream_answer() yield SSE 事件(faq/talk/script 流式,complex 整段)。
"""
import json
import logging
import time
from typing import Dict, Generator, List, Optional

from agent.llm import chat, chat_stream
from agent.prompts import (
    CONSULTANT_SYSTEM, FAQ_PROMPT, QUERY_REWRITE_PROMPT,
    SCRIPT_PROMPT, TALK_PROMPT,
)
from agent.router import classify
from cache import faq_cache, normalize_query

logger = logging.getLogger(__name__)


def _format_history(history: List[Dict]) -> str:
    lines = []
    for h in history[-6:]:
        role = {"user": "用户", "assistant": "助手"}.get(h.get("role", ""), h.get("role", ""))
        lines.append(f"{role}: {h.get('content', '')}")
    return "\n".join(lines)


def _has_history(history: Optional[List[Dict]]) -> bool:
    return bool(history and len(history) > 0)

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": "检索星芽知识库。查询课程体系、价格、校区、师资、试听课、赛事、"
                           "升学规划、课酬、话术规范等内部资料时使用。"
                           "category 可选值:企业基础/客户服务/课程产品/教务运营/品牌输出/学员规划/原始素材",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索问题,具体明确"},
                    "category": {"type": "string", "description": "限定分类,不确定可不传"},
                },
                "required": ["query"],
            },
        },
    }
]


class LemengAgent:
    def __init__(self, retriever):
        self.retriever = retriever

    # ── 公共 ──
    @staticmethod
    def _format_context(docs: List[dict], max_chars: int = 6000) -> str:
        parts, total = [], 0
        for d in docs:
            meta = d.get("metadata", {})
            head = f"[{meta.get('title', '')} | {meta.get('category', '')}]"
            piece = f"{head}\n{d['text']}"
            if total + len(piece) > max_chars:
                break
            parts.append(piece)
            total += len(piece)
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _sources(docs: List[dict]) -> List[str]:
        seen, out = set(), []
        for d in docs:
            meta = d.get("metadata", {})
            label = f"{meta.get('title', '')}({meta.get('source', '')})"
            if label not in seen:
                seen.add(label)
                out.append(label)
        return out

    def _rewrite_query(self, query: str, history: Optional[List[Dict]]) -> str:
        """多轮场景下把代词/省略补全为自包含检索 query"""
        if not _has_history(history):
            return query
        try:
            out = chat(
                [{"role": "user", "content": QUERY_REWRITE_PROMPT.format(
                    history=_format_history(history), query=query)}],
                temperature=0.0, max_tokens=120,
            )
            rewritten = (out.get("content") or query).strip().strip('"').strip("'")
            return rewritten if rewritten else query
        except Exception as e:
            logger.warning("查询改写失败,使用原句: %s", e)
            return query

    def _retrieve_multi(self, queries: List[tuple], cap: int = 10) -> List[dict]:
        """多路检索合并去重,保持顺序优先级(多路本身即扩展,不再叠加 HyDE)"""
        seen, merged = set(), []
        for q, cat in queries:
            for d in self.retriever.retrieve(q, top_k=5, category=cat, hyde=False):
                if d["text"] not in seen:
                    seen.add(d["text"])
                    merged.append(d)
        return merged[:cap]

    # ── 检索 + prompt 构造(流式/非流式共用)──
    def _prepare(self, route: str, query: str,
                 history: Optional[List[Dict]] = None) -> tuple[List[Dict], List[dict]]:
        history = history or []
        if route == "faq":
            # faq 单轮:启用 HyDE 双路 + 邻接扩展,弥合单轮检索的语义 gap
            rewritten = self._rewrite_query(query, history)
            docs = self.retriever.retrieve(rewritten, top_k=5, hyde=True, expand=True)
            if not docs:
                return list(history) + [{"role": "user", "content": query}], []
            return list(history) + [
                {"role": "system", "content": CONSULTANT_SYSTEM.format(context="")},
                {"role": "user", "content": FAQ_PROMPT.format(
                    context=self._format_context(docs), question=query)},
            ], docs
        if route == "talk":
            rewritten = self._rewrite_query(query, history)
            docs = self._retrieve_multi([
                (rewritten, None),
                ("试听课话术 家长沟通 课程价格 促成", "客户服务"),
                ("课程卖点 竞品差异 学员案例", "课程产品"),
            ])
            return list(history) + [{"role": "user", "content": TALK_PROMPT.format(
                context=self._format_context(docs), scene=query)}], docs
        # script
        rewritten = self._rewrite_query(query, history)
        docs = self._retrieve_multi([
            (rewritten, None),
            ("短视频选题 IP打造 获客 内容方向", "品牌输出"),
            ("课程亮点 学员成果 家长反馈", "课程产品"),
        ])
        return list(history) + [{"role": "user", "content": SCRIPT_PROMPT.format(
            context=self._format_context(docs), topic=query)}], docs

    # ── faq(带缓存)──
    def answer_faq(self, question: str, history: Optional[List[Dict]] = None) -> dict:
        has_history = _has_history(history)
        if not has_history:
            key = normalize_query(question)
            cached = faq_cache.get(key)
            if cached:
                return {**cached, "cached": True}

        messages, docs = self._prepare("faq", question, history)
        if not docs:
            result = {"answer": "知识库中暂无相关信息,请联系校区同事补充资料。",
                      "sources": [], "route": "faq"}
        else:
            result = {"answer": chat(messages)["content"],
                      "sources": self._sources(docs), "route": "faq"}
        if not has_history:
            faq_cache.set(normalize_query(question), result)
        return result

    # ── talk ──
    def gen_talk(self, scene: str, history: Optional[List[Dict]] = None) -> dict:
        messages, docs = self._prepare("talk", scene, history)
        return {"answer": chat(messages)["content"],
                "sources": self._sources(docs), "route": "talk"}

    # ── script ──
    def gen_script(self, topic: str, history: Optional[List[Dict]] = None) -> dict:
        messages, docs = self._prepare("script", topic, history)
        return {"answer": chat(messages)["content"],
                "sources": self._sources(docs), "route": "script"}

    # ── complex(工具循环)──
    def answer_complex(self, question: str, history: Optional[List[Dict]] = None) -> dict:
        messages = list(history or []) + [
            {"role": "system", "content":
                "你是星芽少儿编程的知识助手。回答复杂问题必须先调用 retrieve_knowledge 工具"
                "检索知识库(可多次、换不同关键词),再基于工具结果回答。"
                "只用工具返回的信息,不编造;回答末尾列出用到的文档名。"},
            {"role": "user", "content": question},
        ]
        all_docs: List[dict] = []

        for iteration in range(4):
            msg = chat(messages, tools=TOOLS_SPEC, complex_channel=True)  # complex 专用模型(LLM_MODEL_COMPLEX)
            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                return {"answer": msg["content"], "sources": self._sources(all_docs), "route": "complex"}

            messages.append({
                "role": "assistant",
                "content": msg["content"] or None,
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in tool_calls
                ],
            })

            for tc in tool_calls:
                try:
                    args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                    docs = self.retriever.retrieve(
                        args.get("query", question), top_k=5, category=args.get("category"),
                        hyde=False)  # 工具循环已多轮,不叠加 HyDE
                    all_docs.extend(docs)
                    preview = "\n".join(f"[{d['metadata'].get('title', '')}] {d['text'][:400]}"
                                        for d in docs) or "(无结果)"
                    result = f"检索到 {len(docs)} 条:\n{preview}"
                except Exception as e:
                    result = f"工具执行失败: {e}"
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        return {"answer": "问题较复杂,检索轮次已达上限,请缩小问题范围后重试。",
                "sources": self._sources(all_docs), "route": "complex"}

    # ── 流式(SSE 事件)──
    def stream_answer(self, query: str, mode: str = "auto",
                      history: Optional[List[Dict]] = None) -> Generator[Dict, None, None]:
        """yield {event, data}:meta → delta* → done。complex 无中间流,整段一个 delta。"""
        t0 = time.time()
        has_history = _has_history(history)
        route = mode if mode in ("faq", "talk", "script", "complex") else classify(query, history=history)
        logger.info("[stream] 路由: %s ← %s", route, query[:40])

        if route == "faq" and not has_history:
            key = normalize_query(query)
            cached = faq_cache.get(key)
            if cached:
                yield {"event": "meta", "data": {"route": "faq", "sources": cached["sources"], "cached": True}}
                yield {"event": "delta", "data": {"text": cached["answer"]}}
                yield {"event": "done", "data": {"elapsed": round(time.time() - t0, 2), "cached": True}}
                return

        messages, docs = self._prepare(route, query, history)
        yield {"event": "meta", "data": {"route": route, "sources": self._sources(docs), "cached": False}}

        if not docs and route == "faq":
            answer = "知识库中暂无相关信息,请联系校区同事补充资料。"
            yield {"event": "delta", "data": {"text": answer}}
        else:
            parts = []
            for delta in chat_stream(messages):
                parts.append(delta)
                yield {"event": "delta", "data": {"text": delta}}
            answer = "".join(parts)

        elapsed = round(time.time() - t0, 2)
        if route == "faq" and answer and not has_history:
            faq_cache.set(normalize_query(query), {"answer": answer, "sources": self._sources(docs), "route": "faq"})
        yield {"event": "done", "data": {"elapsed": elapsed, "cached": False}}

    # ── 分流入口 ──
    def handle(self, query: str, mode: str = "auto",
               history: Optional[List[Dict]] = None) -> dict:
        route = mode if mode in ("faq", "talk", "script", "complex") else classify(query, history=history)
        logger.info("路由: %s ← %s", route, query[:40])
        handlers = {
            "faq": self.answer_faq,
            "talk": self.gen_talk,
            "script": self.gen_script,
            "complex": self.answer_complex,
        }
        result = handlers[route](query, history)
        result.setdefault("cached", False)
        return result
