#!/usr/bin/env python3
"""Render concise charts directly from the local evaluation Markdown reports."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parent.parent
PAIRED_REPORT = ROOT / "eval" / "results" / "eval_60_paired_report.md"
BEFORE_AFTER_REPORT = ROOT / "eval" / "results" / "eval_before_after.md"
OUTPUT_DIR = ROOT / "eval" / "charts" / "summary"

BLUE = "#2563EB"
ORANGE = "#D97706"
INK = "#111827"
MUTED = "#6B7280"
GRID = "#E5E7EB"


def configure_fonts() -> None:
    """Register the bundled Chinese font when it is available."""
    font_path = ROOT / "eval" / "fonts" / "msyh.ttc"
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        font_name = font_manager.FontProperties(fname=str(font_path)).get_name()
    else:
        font_name = "sans-serif"
    plt.rcParams.update({
        "font.family": [font_name, "sans-serif"],
        "axes.unicode_minus": False,
        "axes.titleweight": "bold",
    })


def table_after_heading(path: Path, heading: str) -> Dict[str, Tuple[float, float]]:
    """Read a paired-score table whose rows are metric | A | B | delta."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"### {heading}")
    rows: Dict[str, Tuple[float, float]] = {}
    in_table = False
    for line in lines[start + 1:]:
        if line.startswith("### "):
            break
        if line.startswith("| 维度 |"):
            in_table = True
            continue
        if in_table and not line.startswith("|"):
            break
        if not in_table or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 3:
            rows[cells[0]] = (float(cells[1]), float(cells[2]))
    if not rows:
        raise ValueError(f"未读取到评测表：{heading}")
    return rows


def read_before_after(path: Path) -> Dict[str, Tuple[float, float]]:
    """Read overall FAQ before/after scores from the local report."""
    rows: Dict[str, Tuple[float, float]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| 总体(60题) |"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows[cells[1]] = (float(cells[2]), float(cells[3]))
    if not rows:
        raise ValueError("未读取到 FAQ 优化前后总体数据")
    return rows


def add_bar_labels(axis: plt.Axes, bars: List[plt.Rectangle]) -> None:
    """Place one-decimal value labels above vertical bars."""
    for bar in bars:
        value = bar.get_height()
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 1.2,
            f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
            color=INK,
        )


def style_axis(axis: plt.Axes) -> None:
    """Apply a quiet, consistent visual treatment."""
    axis.set_axisbelow(True)
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color("#9CA3AF")
    axis.tick_params(colors=INK)


def chart_overall(scores: Dict[str, Tuple[float, float]]) -> None:
    """Render the overall six-metric comparison for the 60-question evaluation."""
    metrics = ["召回率", "完整性", "准确率", "幻觉控制", "检索耗时", "综合"]
    values_a = [scores[metric][0] for metric in metrics]
    values_b = [scores[metric][1] for metric in metrics]
    x = list(range(len(metrics)))
    fig, axis = plt.subplots(figsize=(12, 6.4))
    bars_a = axis.bar([item - 0.19 for item in x], values_a, 0.38, color=BLUE, label="纯 RAG（faq）")
    bars_b = axis.bar([item + 0.19 for item in x], values_b, 0.38, color=ORANGE, label="Agent（complex）")
    add_bar_labels(axis, list(bars_a))
    add_bar_labels(axis, list(bars_b))
    axis.set_xticks(x, metrics)
    axis.set_ylim(0, 108)
    axis.set_ylabel("得分（百分制）")
    axis.set_title("60 题总体评测：纯 RAG 与 Agent")
    axis.legend(frameon=False, ncol=2, loc="upper left")
    style_axis(axis)
    fig.text(0.125, 0.02, "n=60；检索耗时为得分，分数越高表示耗时表现越好。来源：eval_60_paired_report.md", color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(OUTPUT_DIR / "01_overall_rag_vs_agent.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def chart_type_advantage(scores: List[Tuple[str, int, float]]) -> None:
    """Render Agent's composite-score advantage by question type."""
    names = [item[0] for item in scores]
    counts = [item[1] for item in scores]
    deltas = [item[2] for item in scores]
    fig, axis = plt.subplots(figsize=(10.5, 6.5))
    bars = axis.barh(names, deltas, color=BLUE, height=0.58)
    axis.invert_yaxis()
    axis.axvline(0, color=INK, linewidth=0.9)
    axis.set_xlim(0, max(deltas) + 5)
    axis.set_xlabel("综合分差值（Agent − 纯 RAG，百分点）")
    axis.set_title("各题型综合分差值")
    for bar, delta, count in zip(bars, deltas, counts):
        axis.text(delta + 0.35, bar.get_y() + bar.get_height() / 2, f"+{delta:.1f}  (n={count})", va="center", fontsize=10, color=INK)
    style_axis(axis)
    fig.text(0.125, 0.02, "所有数值均取自 60 题配对评测；正值表示 Agent 综合分更高。来源：eval_60_paired_report.md", color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(OUTPUT_DIR / "02_agent_advantage_by_type.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def chart_faq_optimization(scores: Dict[str, Tuple[float, float]]) -> None:
    """Render FAQ quality and score trade-offs before and after optimization."""
    quality = ["召回率", "完整性", "准确率", "幻觉控制"]
    all_metrics = ["检索耗时", "综合"]
    fig, (left, right) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [2.2, 1]})
    x = list(range(len(quality)))
    before = [scores[metric][0] for metric in quality]
    after = [scores[metric][1] for metric in quality]
    bars_before = left.bar([item - 0.19 for item in x], before, 0.38, color=BLUE, label="优化前")
    bars_after = left.bar([item + 0.19 for item in x], after, 0.38, color=ORANGE, label="优化后")
    add_bar_labels(left, list(bars_before))
    add_bar_labels(left, list(bars_after))
    left.set_xticks(x, quality)
    left.set_ylim(0, 108)
    left.set_ylabel("得分（百分制）")
    left.set_title("质量指标")
    left.legend(frameon=False, ncol=2, loc="upper left")
    style_axis(left)

    for index, metric in enumerate(all_metrics):
        before_value, after_value = scores[metric]
        right.plot([before_value, after_value], [index, index], color="#9CA3AF", linewidth=1.8, zorder=1)
        right.scatter([before_value], [index], color=BLUE, s=70, zorder=2)
        right.scatter([after_value], [index], color=ORANGE, s=70, zorder=2)
        right.text(before_value, index + 0.16, f"{before_value:.1f}", ha="center", va="bottom", color=BLUE, fontsize=9)
        right.text(after_value, index - 0.16, f"{after_value:.1f}", ha="center", va="top", color=ORANGE, fontsize=9)
    right.set_yticks(range(len(all_metrics)), all_metrics)
    right.set_xlim(55, 105)
    right.set_xlabel("得分（百分制）")
    right.set_title("耗时与综合")
    right.grid(axis="x", color=GRID, linewidth=0.8)
    right.spines[["top", "right", "left"]].set_visible(False)
    right.tick_params(colors=INK)
    fig.suptitle("FAQ 通道优化前后：60 题总体", y=1.01, fontsize=15, fontweight="bold")
    fig.text(0.125, 0.01, "检索耗时与综合均为评测得分；来源：eval_before_after.md", color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.savefig(OUTPUT_DIR / "03_faq_before_after.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    """Build all evaluation-summary visuals from the Markdown source files."""
    configure_fonts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    overall = table_after_heading(PAIRED_REPORT, "总体(60题)(n=60)")
    type_sections = [
        ("单点查询", 21), ("场景型", 9), ("多跳推理", 3), ("对比型", 6),
        ("流程型", 5), ("计算型", 6), ("边界异常", 10),
    ]
    type_deltas = []
    for name, count in type_sections:
        values = table_after_heading(PAIRED_REPORT, f"题型:{name}(n={count})")
        baseline, agent = values["综合"]
        type_deltas.append((name, count, round(agent - baseline, 1)))
    chart_overall(overall)
    chart_type_advantage(type_deltas)
    chart_faq_optimization(read_before_after(BEFORE_AFTER_REPORT))


if __name__ == "__main__":
    main()
