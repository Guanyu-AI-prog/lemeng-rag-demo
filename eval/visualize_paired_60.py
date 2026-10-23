#!/usr/bin/env python3
"""配对评测可视化:从 eval60_progress.json 出 4 张图到 eval/charts/

用法: python eval/visualize_paired_60.py
"""
import json
import os
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "eval"))
from sample_questions import TEST_CASES

PROGRESS_FILE = os.path.join(BASE_DIR, "eval", "results", "eval60_progress.json")
CHART_DIR = os.path.join(BASE_DIR, "eval", "charts")

DIMS = ["recall", "completeness", "accuracy", "hallucination", "latency_score", "composite"]
DIM_NAMES = ["召回率", "完整性", "准确率", "幻觉控制", "检索耗时", "综合"]

# 中文字体:优先项目内 fonts/(从 Windows 拷贝的 msyh.ttc),其次系统字体
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
if os.path.isdir(_FONT_DIR):
    for f in os.listdir(_FONT_DIR):
        if f.endswith((".ttc", ".ttf", ".otf")):
            font_manager.fontManager.addfont(os.path.join(_FONT_DIR, f))
for f in font_manager.findSystemFonts(fontpaths=None):
    if any(k in f for k in ("wqy", "noto", "NotoSansCJK", "droid")):
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["Microsoft YaHei", "WenQuanYi Zen Hei", "Noto Sans CJK SC", "Droid Sans Fallback", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

A_COLOR, B_COLOR = "#1f77b4", "#ff7f0e"


def load():
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def avg(vals):
    return round(statistics.mean(vals), 1) if vals else 0


def collect(progress, cases):
    rows = []
    for tc in cases:
        a = progress["A"].get(str(tc["id"]))
        b = progress["B"].get(str(tc["id"]))
        if a and b and "scores" in a and "scores" in b:
            rows.append((tc, a["scores"], b["scores"]))
    return rows


def chart_overall(progress):
    rows = collect(progress, TEST_CASES)
    vals_a = [avg([s[d] for _, s, _ in rows]) for d in DIMS]
    vals_b = [avg([s[d] for _, _, s in rows]) for d in DIMS]
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(DIMS))
    ax.bar([i - 0.2 for i in x], vals_a, 0.4, label="纯RAG(faq)", color=A_COLOR)
    ax.bar([i + 0.2 for i in x], vals_b, 0.4, label="Agent(complex)", color=B_COLOR)
    ax.set_xticks(list(x), DIM_NAMES)
    ax.set_ylim(0, 105)
    ax.set_title(f"五维对比(总体,n={len(rows)})")
    ax.legend()
    for i, (va, vb) in enumerate(zip(vals_a, vals_b)):
        ax.text(i - 0.2, va + 1, str(va), ha="center", fontsize=8)
        ax.text(i + 0.2, vb + 1, str(vb), ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "01_overall_5dim.png"), dpi=120)
    plt.close(fig)


def chart_radar(progress):
    rows = collect(progress, TEST_CASES)
    dims, names = DIMS[:-1], DIM_NAMES[:-1]  # 综合不入雷达
    vals_a = [avg([s[d] for _, s, _ in rows]) for d in dims]
    vals_b = [avg([s[d] for _, _, s in rows]) for d in dims]
    import math
    angles = [i / len(dims) * 2 * math.pi for i in range(len(dims))] + [0]
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})
    ax.plot(angles, vals_a + vals_a[:1], color=A_COLOR, label="纯RAG(faq)")
    ax.fill(angles, vals_a + vals_a[:1], color=A_COLOR, alpha=0.2)
    ax.plot(angles, vals_b + vals_b[:1], color=B_COLOR, label="Agent(complex)")
    ax.fill(angles, vals_b + vals_b[:1], color=B_COLOR, alpha=0.2)
    ax.set_xticks(angles[:-1], names)
    ax.set_ylim(0, 100)
    ax.set_title("能力雷达(总体)")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "02_radar.png"), dpi=120)
    plt.close(fig)


def chart_by_type(progress):
    types = sorted({t["type"] for t in TEST_CASES})
    diff_data = {t: [] for t in types}
    for tc in TEST_CASES:
        a = progress["A"].get(str(tc["id"]))
        b = progress["B"].get(str(tc["id"]))
        if a and b and "scores" in a and "scores" in b:
            diff_data[tc["type"]].append(b["scores"]["composite"] - a["scores"]["composite"])
    diffs = [avg(diff_data[t]) for t in types]
    counts = [len(diff_data[t]) for t in types]
    colors = [B_COLOR if d > 0 else A_COLOR for d in diffs]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(types, diffs, color=colors)
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title("综合分配对差值(Agent−纯RAG) 按题型(>0 Agent 占优)")
    for i, (d, c) in enumerate(zip(diffs, counts)):
        ax.text(i, (d or 0) + (0.5 if d >= 0 else -1.5), f"{d} (n={c})", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "03_paired_diff_by_type.png"), dpi=120)
    plt.close(fig)


def chart_latency(progress):
    rows = collect(progress, TEST_CASES)
    ids = [tc["id"] for tc, _, _ in rows]
    ra = [progress["A"][str(tc["id"])]["retrieval"]["retrieval_elapsed"] for tc, _, _ in rows]
    rb = [progress["B"][str(tc["id"])]["retrieval"]["retrieval_elapsed"] for tc, _, _ in rows]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(ids, ra, "o-", color=A_COLOR, label="纯RAG(faq)", ms=4)
    ax.plot(ids, rb, "s-", color=B_COLOR, label="Agent(complex)", ms=4)
    ax.set_xlabel("题目 id")
    ax.set_ylabel("检索耗时(秒)")
    ax.set_title("每题检索耗时(证据捕获层)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "04_latency.png"), dpi=120)
    plt.close(fig)


def chart_by_group(progress):
    """A/B/C 组别的双通道综合分对比"""
    groups = sorted({t["group"] for t in TEST_CASES})
    labels = {"A": "A组·锚点(1-30)", "B": "B组·进阶(31-60)", "C": "C组·扩充(61-120)"}
    va, vb, ns = [], [], []
    for g in groups:
        rows = [(s_a, s_b) for t, s_a, s_b in
                [(t, progress["A"].get(str(t["id"]), {}).get("scores"),
                  progress["B"].get(str(t["id"]), {}).get("scores"))
                 for t in TEST_CASES if t["group"] == g]
                if s_a and s_b]
        va.append(avg([x["composite"] for x, _ in rows]))
        vb.append(avg([x["composite"] for _, x in rows]))
        ns.append(len(rows))
    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(groups))
    ax.bar([i - 0.2 for i in x], va, 0.4, label="纯RAG(faq)", color=A_COLOR)
    ax.bar([i + 0.2 for i in x], vb, 0.4, label="Agent(complex)", color=B_COLOR)
    ax.set_xticks(list(x), [f"{labels[g]}\n(n={n})" for g, n in zip(groups, ns)], fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_title("双通道综合分 · 按题组")
    ax.legend()
    for i, (a, b) in enumerate(zip(va, vb)):
        ax.text(i - 0.2, a + 1, str(a), ha="center", fontsize=9)
        ax.text(i + 0.2, b + 1, str(b), ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "05_by_group.png"), dpi=120)
    plt.close(fig)


def main():
    if not os.path.exists(PROGRESS_FILE):
        sys.exit("无进度文件")
    progress = load()
    os.makedirs(CHART_DIR, exist_ok=True)
    chart_overall(progress)
    chart_radar(progress)
    chart_by_type(progress)
    chart_latency(progress)
    chart_by_group(progress)
    print(f"图表已生成: {CHART_DIR}/")


if __name__ == "__main__":
    main()
