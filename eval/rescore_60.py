#!/usr/bin/env python3
"""重算 progress.json 里全部分数(答案与检索证据已存,无需重新调用 LLM)

用法: python eval/rescore_60.py
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "eval"))

from eval_paired_60 import score_case, PROGRESS_FILE
from sample_questions import TEST_CASES

with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
    progress = json.load(f)

tc_by_id = {t["id"]: t for t in TEST_CASES}
changed = 0
for pl in ("A", "B"):
    for key, r in progress[pl].items():
        if "scores" not in r:
            continue
        tc = tc_by_id[int(key)]
        new = score_case(tc, r["answer"], r["retrieval"])
        if new != r["scores"]:
            changed += 1
        r["scores"] = new

tmp = PROGRESS_FILE + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(progress, f, ensure_ascii=False, indent=1)
os.replace(tmp, PROGRESS_FILE)
print(f"重算完成,变更 {changed} 题次")
