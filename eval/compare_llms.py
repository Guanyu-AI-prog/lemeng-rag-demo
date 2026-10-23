#!/usr/bin/env python3
"""多模型锚点筛选对比:汇总各模型的锚点30题五维成绩 + deepseek-chat 基线

用法: python eval/compare_llms.py [模型progress文件...]
无参数时自动扫描 eval/results/eval60_progress_*.json + 主基线
"""
import glob
import json
import os
import statistics
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "eval"))
from sample_questions import TEST_CASES

RESULTS_DIR = os.path.join(BASE_DIR, "eval", "results")
ANCHOR_IDS = {str(t["id"]) for t in TEST_CASES if t["group"] == "A"}
ALL_IDS = {str(t["id"]) for t in TEST_CASES}
DIMS = ["recall", "completeness", "accuracy", "hallucination", "latency_score", "composite"]
DIM_NAMES = ["召回率", "完整性", "准确率", "幻觉控制", "检索耗时", "综合"]


def avg(vals):
    return round(statistics.mean(vals), 1) if vals else 0.0


def model_stats(path, ids=None):
    scope = ids or ALL_IDS
    with open(path, "r", encoding="utf-8") as f:
        p = json.load(f)
    rows_a = [p["A"][k]["scores"] for k in scope if k in p["A"] and "scores" in p["A"][k]]
    rows_b = [p["B"][k]["scores"] for k in scope if k in p["B"] and "scores" in p["B"][k]]
    # 端到端延迟(生成+检索全程)
    e2e_a = [p["A"][k].get("e2e_seconds", 0) for k in scope if k in p["A"] and "scores" in p["A"][k]]
    e2e_b = [p["B"][k].get("e2e_seconds", 0) for k in scope if k in p["B"] and "scores" in p["B"][k]]
    return {
        "n_a": len(rows_a), "n_b": len(rows_b),
        "A": {d: avg([s[d] for s in rows_a]) for d in DIMS},
        "B": {d: avg([s[d] for s in rows_b]) for d in DIMS},
        "e2e_avg_a": avg(e2e_a), "e2e_avg_b": avg(e2e_b),
    }


def main():
    full = "--full" in sys.argv
    files = [a for a in sys.argv[1:] if not a.startswith("--")] or (
        [os.path.join(RESULTS_DIR, "eval60_progress.json")] +
        sorted(glob.glob(os.path.join(RESULTS_DIR, "eval60_progress_*.json")))
    )
    scope_ids = ALL_IDS if full else ANCHOR_IDS
    scope_name = "120题全量" if full else "锚点30题"
    models = {}
    for fp in files:
        if not os.path.exists(fp):
            continue
        base = os.path.basename(fp)
        if base == "eval60_progress.json":
            name = "deepseek-chat(现役基线)"
        elif base == "eval60_progress_baseline.json":
            name = "旧基线备份(HyDE前A通道)"
        else:
            name = base.replace("eval60_progress_", "").replace(".json", "").replace("_", "/")
        try:
            models[name] = model_stats(fp, scope_ids)
        except Exception as e:
            print(f"跳过 {fp}: {e}")

    # 报告:每模型 A/B 通道综合 + 明细
    out = [f"# 多模型对比({scope_name},A+B双通道)\n",
           "| 模型 | 通道 | 召回 | 完整 | 准确 | 幻觉 | 耗时分 | 综合 | 端到端均耗时 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for name, st in models.items():
        for ch in ("A", "B"):
            d = st[ch]
            e2e = st["e2e_avg_a"] if ch == "A" else st["e2e_avg_b"]
            out.append(f"| {name} | {ch} | {d['recall']} | {d['completeness']} | {d['accuracy']} "
                       f"| {d['hallucination']} | {d['latency_score']} | **{d['composite']}** | {e2e}s |")

    # 综合排名(A+B 均值)
    out.append("\n## 综合排名(A/B 均值)\n")
    rank = sorted(models.items(), key=lambda kv: -(kv[1]["A"]["composite"] + kv[1]["B"]["composite"]) / 2)
    for i, (name, st) in enumerate(rank, 1):
        mean = round((st["A"]["composite"] + st["B"]["composite"]) / 2, 1)
        out.append(f"{i}. **{name}** — 综合 {mean}")

    text = "\n".join(out)
    print(text)
    dest = os.path.join(RESULTS_DIR, "llm_screen_report.md")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\n已保存: {dest}")


if __name__ == "__main__":
    main()
