#!/usr/bin/env python3
"""从 eval/results/eval60_progress.json 生成配对评测报告(markdown)

用法: python eval/eval_paired_report.py
"""
import json
import os
import statistics
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "eval"))
from sample_questions import TEST_CASES

PROGRESS_FILE = os.path.join(BASE_DIR, "eval", "results", "eval60_progress.json")
REPORT_FILE = os.path.join(BASE_DIR, "eval", "results", "eval_60_paired_report.md")

DIMS = ["recall", "completeness", "accuracy", "hallucination", "latency_score", "composite"]
DIM_NAMES = {"recall": "召回率", "completeness": "完整性", "accuracy": "准确率",
             "hallucination": "幻觉控制", "latency_score": "检索耗时", "composite": "综合"}


def avg(vals):
    return round(statistics.mean(vals), 1) if vals else None


def dim_table(progress, cases, title):
    rows = []
    for tc in cases:
        a = progress["A"].get(str(tc["id"]))
        b = progress["B"].get(str(tc["id"]))
        if a and b and "scores" in a and "scores" in b:
            rows.append((tc, a["scores"], b["scores"]))
    if not rows:
        return f"\n### {title}\n\n(无已完成数据)\n"
    lines = [f"\n### {title}(n={len(rows)})\n",
             "| 维度 | 纯RAG(A) | Agent(B) | 差值(B−A) |", "|---|---|---|---|"]
    for dim in DIMS:
        va = [s[dim] for _, s, _ in rows]
        vb = [s[dim] for _, _, s in rows]
        aa, ab = avg(va), avg(vb)
        diff = round(ab - aa, 1) if aa is not None and ab is not None else "-"
        lines.append(f"| {DIM_NAMES[dim]} | {aa} | {ab} | {diff} |")
    return "\n".join(lines) + "\n"


def main():
    if not os.path.exists(PROGRESS_FILE):
        sys.exit("无进度文件,先跑 eval_paired_60.py")
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        progress = json.load(f)

    group_a = [t for t in TEST_CASES if t["group"] == "A"]
    group_b = [t for t in TEST_CASES if t["group"] == "B"]
    group_c = [t for t in TEST_CASES if t["group"] == "C"]
    types = sorted({t["type"] for t in TEST_CASES})

    out = [f"# 星芽知识库 120 题配对评测报告:纯RAG(faq) vs Agent(complex)",
           f"",
           f"> 生成时间:{datetime.now():%Y-%m-%d %H:%M}  ",
           f"> A 通道 = mode=faq(混合检索+单轮生成);B 通道 = mode=complex(Agent 工具循环多步检索)  ",
           f"> 五维百分制客观公式:召回率(检索层)/完整性(答案层)/幻觉控制/准确率/检索耗时,综合=等权平均  ",
           f"> 限流重试累计:{progress.get('stats', {}).get('rate_limit_retries', 0)} 次",
           dim_table(progress, TEST_CASES, "总体(120题)"),
           dim_table(progress, group_a, "A组(原30题)"),
            dim_table(progress, group_b, "B组(新30题)"),
            dim_table(progress, group_c, "C组(新60题,61-120)")]
    for t in types:
        out.append(dim_table(progress, [x for x in TEST_CASES if x["type"] == t], f"题型:{t}"))

    # 幻觉明细
    out.append("\n## 幻觉点明细(anti 命中 / 无出处数字)\n")
    out.append("| 题 | 通道 | anti命中 | 脑补数字 | 答案摘要 |")
    out.append("|---|---|---|---|---|")
    for tc in TEST_CASES:
        for pl in ("A", "B"):
            r = progress[pl].get(str(tc["id"]))
            if r and r.get("scores") and (r["scores"].get("anti_hits", 0) or r["scores"].get("fabricated_numbers", 0)):
                ans = r["answer"][:60].replace("\n", " ").replace("|", "/")
                out.append(f"| {tc['id']} | {pl} | {r['scores']['anti_hits']} | "
                           f"{r['scores']['fabricated_numbers']} | {ans} |")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"报告已生成: {REPORT_FILE}")
    print("\n".join(out[:22]))


if __name__ == "__main__":
    main()
