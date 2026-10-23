#!/usr/bin/env python3
"""对比 A 通道(纯RAG/faq)优化前后的 60 题评测结果

用法: python eval/compare_before_after.py [baseline.json] [after.json]
默认: baseline=eval60_progress_baseline.json, after=eval60_progress.json
"""
import json
import os
import statistics
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "eval"))
from sample_questions import TEST_CASES

DIMS = ["recall", "completeness", "accuracy", "hallucination", "latency_score", "composite"]
DIM_NAMES = ["召回率", "完整性", "准确率", "幻觉控制", "检索耗时", "综合"]


def avg(vals):
    return round(statistics.mean(vals), 1) if vals else 0.0


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def channel_means(progress, channel, cases):
    rows = []
    for tc in cases:
        r = progress[channel].get(str(tc["id"]))
        if r and "scores" in r:
            rows.append(r["scores"])
    return {d: avg([s[d] for s in rows]) for d in DIMS}, len(rows)


def main():
    base_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "eval", "results", "eval60_progress_baseline.json")
    after_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE_DIR, "eval", "results", "eval60_progress.json")
    base, after = load(base_path), load(after_path)

    groups = [("总体(60题)", TEST_CASES),
              ("A组(1-30)", [t for t in TEST_CASES if t["group"] == "A"]),
              ("B组(31-60)", [t for t in TEST_CASES if t["group"] == "B"])]

    out = ["# A 通道(纯RAG/faq)优化前后对比\n",
           "| 范围 | 维度 | 优化前 | 优化后 | 差值 |", "|---|---|---|---|---|"]
    for title, cases in groups:
        m_before, n1 = channel_means(base, "A", cases)
        m_after, n2 = channel_means(after, "A", cases)
        for dim, name in zip(DIMS, DIM_NAMES):
            d = round(m_after[dim] - m_before[dim], 1)
            mark = "↑" if d > 0.5 else ("↓" if d < -0.5 else "≈")
            out.append(f"| {title} | {name} | {m_before[dim]} | {m_after[dim]} | {d:+.1f} {mark} |")
        out.append("|---|---|---|---|---|")

    text = "\n".join(out)
    print(text)
    report = os.path.join(BASE_DIR, "eval", "results", "eval_before_after.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\n已保存: {report}")


if __name__ == "__main__":
    main()
