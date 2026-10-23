#!/usr/bin/env python3
"""星芽知识库 60 题配对评测:纯RAG(faq 通道) vs Agent(complex 通道)

改编自 rag-agent-system/evaluation/scripts/eval_rag_vs_agent_60.py,适配 lemeng-rag:
- A 通道 = handle(mode="faq"):混合检索 + 课程顾问生成(纯 RAG fast-path)
- B 通道 = handle(mode="complex"):Agent 工具循环多步检索
- 检索 hook:包装 agent.retriever.retrieve,按题记录 chunk 与耗时(不改业务代码)
- faq TTL 缓存在评测前清空,保证检索真实发生
- 断点续跑:eval/results/eval60_progress.json;限流指数退避
- 五维百分制(客观公式,无人工打分):
    召回率   = expected_keywords 在检索上下文中的命中比例 ×100
    完整性   = expected_keywords 在最终答案中的命中比例 ×100
    幻觉控制 = 100 − 50×幻觉点;幻觉点 = anti 命中(非否定语境)+ 无出处数字,上限2
    准确率   = 完整性 × (1 − 幻觉点/2)
    检索耗时 = t≤3s→100;t≥15s→0;线性
    综合     = 五维等权平均

用法:
    python eval/eval_paired_60.py --check            # 题库核定:只跑检索,报告关键词命中率
    python eval/eval_paired_60.py --limit 4          # 冒烟:前4题双通道
    python eval/eval_paired_60.py                    # 全量 60×2
    python eval/eval_paired_60.py --qids 35,41       # 指定题
"""
import argparse
import json
import os
import re
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "eval"))

from sample_questions import TEST_CASES

RESULTS_DIR = os.path.join(BASE_DIR, "eval", "results")


def progress_file(llm: str = None) -> str:
    """无 --llm → 主基线 progress.json;--llm → 按模型分档,不污染 deepseek 基线"""
    if not llm:
        return os.path.join(RESULTS_DIR, "eval60_progress.json")
    slug = llm.replace("/", "_").replace(".", "_")
    return os.path.join(RESULTS_DIR, f"eval60_progress_{slug}.json")

RATE_LIMIT_PATTERNS = re.compile(
    r"429|rate.?limit|too many requests|限流|请求过快|throttl", re.IGNORECASE)
NUM_RE = re.compile(r"\d+(?:\.\d+)?")

# 否定语境词:anti_keyword 出现在含否定词的句子中不算幻觉("星芽没有Python课程"是正确表述)
NEGATION_WORDS = ["没有", "未开设", "不开", "不设", "暂无", "不教", "不建议", "不是",
                  "并非", "并无", "无", "非", "别", "未提供", "不直接", "不再", "未引入",
                  "不经", "不需", "不学", "不用", "无需", "不引入", "绕开", "绕过",
                  "避开", "跳过", "排除", "不迁", "不搞", "不做", "不推", "未引入"]


def with_rate_limit_retry(fn, max_retries=6, base_delay=8.0, stats=None):
    for attempt in range(max_retries + 1):
        try:
            return fn(), None
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            if RATE_LIMIT_PATTERNS.search(msg) and attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), 120.0)
                if stats is not None:
                    stats["rate_limit_retries"] = stats.get("rate_limit_retries", 0) + 1
                print(f"    ⚠️ 疑似限流({msg[:90]}),退避 {delay:.0f}s 后重试 ({attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            raise
    return None, "max_retries_exceeded"


class RetrievalRecorder:
    """包装 LemengAgent.retriever.retrieve,按题记录检索证据与耗时"""

    def __init__(self, retriever):
        self._retriever = retriever
        self.calls = []

    def start_question(self):
        self.calls = []

    def collect(self):
        chunks, elapsed = [], 0.0
        seen = set()
        for c in self.calls:
            elapsed += c["elapsed"]
            for d in c["docs"]:
                key = d["text"]
                if key in seen:
                    continue
                seen.add(key)
                chunks.append({"content": d["text"],
                               "source": d.get("metadata", {}).get("source", "")})
        return {"chunks": chunks, "retrieval_elapsed": round(elapsed, 3),
                "n_calls": len(self.calls)}

    def wrap(self):
        orig = self._retriever.retrieve

        def wrapped(query, top_k=5, category=None, *a, **kw):
            t = time.time()
            docs = orig(query, top_k=top_k, category=category, *a, **kw)
            self.calls.append({"query": query, "docs": list(docs or []),
                               "elapsed": time.time() - t})
            return docs

        self._retriever.retrieve = wrapped


# ── 评分 ──
def _anti_fires(answer: str, anti_kw: str) -> bool:
    """anti_keyword 在非否定语境的句子中出现才算幻觉点"""
    for sentence in re.split(r"[。!?;\n]", answer):
        if anti_kw in sentence and not any(w in sentence for w in NEGATION_WORDS):
            return True
    return False


def score_case(tc, answer, retrieval):
    keywords = tc.get("expected_keywords", [])
    anti = tc.get("anti_keywords", [])
    context_text = "\n".join(c["content"] for c in retrieval["chunks"])

    total = max(1, len(keywords))
    hit_ctx = sum(1 for k in keywords if k in context_text)
    hit_ans = sum(1 for k in keywords if k in answer)
    recall = round(hit_ctx / total * 100, 1)
    completeness = round(hit_ans / total * 100, 1)

    anti_hits = sum(1 for k in anti if _anti_fires(answer, k))

    # 无出处数字:答案中的数字不在 检索上下文/参考答案/关键词 任何一处 → 脑补
    fabricated = 0
    if context_text:
        scope = context_text + " " + tc.get("reference", "") + " " + " ".join(keywords)
        for m in set(NUM_RE.findall(answer)):
            if len(m) >= 2 and m not in scope and not any(m in w for w in keywords):
                fabricated += 1
    points = min(2, anti_hits + fabricated)
    hallucination_score = max(0.0, 100 - 50 * points)
    accuracy = round(completeness * (1 - points / 2), 1)

    t = retrieval["retrieval_elapsed"]
    if t <= 3:
        latency = 100.0
    elif t >= 15:
        latency = 0.0
    else:
        latency = round(100 * (15 - t) / 12, 1)

    composite = round((recall + completeness + accuracy + hallucination_score + latency) / 5, 1)

    return {
        "recall": recall, "completeness": completeness, "accuracy": accuracy,
        "hallucination": round(hallucination_score, 1), "latency_score": latency,
        "composite": composite,
        "hit_context": f"{hit_ctx}/{total}", "hit_answer": f"{hit_ans}/{total}",
        "anti_hits": anti_hits, "fabricated_numbers": fabricated,
    }


def load_progress(prog_file: str):
    if os.path.exists(prog_file):
        with open(prog_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"A": {}, "B": {}, "stats": {}}


def save_progress(progress, prog_file: str):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    tmp = prog_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=1)
    os.replace(tmp, prog_file)


# ── 题库核定模式在 main 的 --check 分支实现 ──


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipelines", default="A,B")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--qids", default="")
    ap.add_argument("--group", default="", help="按组筛选:A/B/C(锚点/进阶/扩充)")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--check", action="store_true", help="题库核定:只检索并报告关键词命中率")
    ap.add_argument("--llm", default="", help="SiliconFlow 模型名(如 deepseek-ai/DeepSeek-V3.2),"
                                             "端点与 key 自动切 SiliconFlow,max_tokens 提到 8000;"
                                             "结果存独立 progress_<model>.json,不污染 deepseek 基线")
    args = ap.parse_args()

    from config import Config
    if args.llm:
        # 多模型对比:统一走 SiliconFlow 端点;思考型模型需大 max_tokens 防正文被思考吃光
        Config.LLM_MODEL = args.llm
        Config.LLM_API_BASE = Config.SILICONFLOW_API_BASE
        Config.LLM_API_KEY = Config.SILICONFLOW_API_KEY
        Config.LLM_MAX_TOKENS = 8000
    Config.validate()
    from retrieval.bm25 import BM25Index
    from retrieval.embedder import Embedder
    from retrieval.hybrid import HybridRetriever
    from retrieval.reranker import Reranker
    from retrieval.vector_store import VectorStore
    from agent.agent import LemengAgent
    from cache import faq_cache

    print("初始化 lemeng-rag ...")
    embedder = Embedder()
    store = VectorStore(embedder)
    retriever = HybridRetriever(store, BM25Index(store.all_records()), Reranker())
    agent = LemengAgent(retriever)

    if args.check:
        # 核定模式:只测原始查询的直查命中(HyDE/邻接关闭,口径真实且快)
        orig_retrieve = retriever.retrieve
        for tc in TEST_CASES:
            docs = orig_retrieve(tc["question"], top_k=10, hyde=False, expand=False)
            context_text = "\n".join(d["text"] for d in docs)
            kws = tc["expected_keywords"]
            hit = [k for k in kws if k in context_text]
            ratio = len(hit) / max(1, len(kws))
            mark = "✅" if ratio >= 0.6 else ("⚠️" if ratio >= 0.34 else "❌")
            missed = "/".join(k for k in kws if k not in hit) or "-"
            print(f"{mark} [{tc['id']:>2}] {tc['type']:<4} 命中{len(hit)}/{len(kws)} 缺:{missed}")
        return

    pipelines = [p.strip().upper() for p in args.pipelines.split(",") if p.strip()]
    cases = TEST_CASES
    if args.qids:
        want = {int(x) for x in args.qids.split(",")}
        cases = [c for c in cases if c["id"] in want]
    elif args.group:
        g = args.group.upper()
        cases = [c for c in cases if c["group"] == g]
    elif args.limit:
        cases = cases[:args.limit]

    prog_file = progress_file(args.llm)
    progress = load_progress(prog_file)
    stats = progress.setdefault("stats", {})
    stats.setdefault("rate_limit_retries", 0)
    if args.llm:
        stats.setdefault("model", args.llm)

    rec = RetrievalRecorder(retriever)
    rec.wrap()

    def run_channel(channel, question):
        faq_cache.clear()  # 评测绕开缓存,保证检索真实发生
        r = agent.handle(question, mode="faq" if channel == "A" else "complex")
        return r["answer"], bool(r.get("success", True)), r.get("elapsed", 0)

    done = 0
    for tc in cases:
        for pl in pipelines:
            key = str(tc["id"])
            if key in progress[pl]:
                continue
            rec.start_question()
            print(f"\n▶ [{pl}{tc['id']}] {tc['question']}")
            t0 = time.time()
            try:
                (answer, success, _e2e), _ = with_rate_limit_retry(
                    lambda: run_channel(pl, tc["question"]), stats=stats)
            except Exception as e:
                print(f"    ❌ 失败: {e}")
                progress[pl][key] = {
                    "question": tc["question"], "answer": f"<<EXEC_ERROR>> {e}",
                    "success": False, "e2e_seconds": round(time.time() - t0, 2),
                    "retrieval": {"chunks": [], "retrieval_elapsed": 0, "n_calls": 0},
                }
                save_progress(progress, prog_file)
                continue

            retrieval = rec.collect()
            score = score_case(tc, answer, retrieval)
            progress[pl][key] = {
                "question": tc["question"], "answer": answer, "success": success,
                "e2e_seconds": round(time.time() - t0, 2), "retrieval": retrieval,
                "scores": score,
            }
            save_progress(progress, prog_file)
            s = score
            print(f"    ✅ {time.time() - t0:.1f}s(端到端) 检索{retrieval['retrieval_elapsed']:.1f}s "
                  f"召回{s['recall']}% 完整{s['completeness']}% 准确{s['accuracy']}% "
                  f"幻觉{s['hallucination']}% 耗时分{s['latency_score']}% 综合{s['composite']}%")
            done += 1
            time.sleep(args.delay)

    total = max(1, len(cases) * len(pipelines))
    print(f"\n本轮新完成 {done} 题次。进度:A={len(progress['A'])}/{len(TEST_CASES)} "
          f"B={len(progress['B'])}/{len(TEST_CASES)}")
    print(f"限流重试累计:{stats.get('rate_limit_retries', 0)}")
    if args.llm:
        print(f"模型:{args.llm} | 进度文件:{prog_file}")


if __name__ == "__main__":
    main()
