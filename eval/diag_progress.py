"""诊断:找 progress 里缺 composite 的记录"""
import json

p = json.load(open("/home/administrator/lemeng-rag/eval/results/eval60_progress.json"))
for pl in ("A", "B"):
    for key, r in p[pl].items():
        if not isinstance(r, dict):
            print(pl, key, "非dict:", type(r))
            continue
        s = r.get("scores")
        if s is None:
            print(pl, key, "无scores | answer:", str(r.get("answer", ""))[:50])
        elif "composite" not in s:
            print(pl, key, "scores缺composite | keys:", list(s.keys()))
