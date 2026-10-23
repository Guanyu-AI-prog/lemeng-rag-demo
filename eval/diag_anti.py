"""查看总体五维 + 检查 anti 误判明细"""
import json
import statistics

p = json.load(open("/home/administrator/lemeng-rag/eval/results/eval60_progress.json"))
for pl in ("A", "B"):
    s = [r["scores"] for r in p[pl].values() if "scores" in r]
    means = {d: round(statistics.mean([x[d] for x in s]), 1)
             for d in ("recall", "completeness", "accuracy", "hallucination", "latency_score", "composite")}
    print(pl, means)

print("\n== anti 命中上下文 ==")
import re
NEG = ["没有", "未开设", "不开", "不设", "暂无", "不教", "不建议", "不是", "并非", "并无", "无", "非", "别", "未提供", "不直接"]
for tc_id, anti_kw in [(31, "Python"), (41, "Python"), (55, "Python")]:
    r = p["A"].get(str(tc_id))
    if not r or not r.get("scores", {}).get("anti_hits"):
        continue
    # 从题库找 anti 词
    import sys
    sys.path.insert(0, "/home/administrator/lemeng-rag/eval")
    from sample_questions import TEST_CASES
    tc = next(t for t in TEST_CASES if t["id"] == tc_id)
    for kw in tc.get("anti_keywords", []):
        for sentence in re.split(r"[。!?;\n]", r["answer"]):
            if kw in sentence and not any(w in sentence for w in NEG):
                print(f"题{tc_id} fire句: {sentence[:120]}")
