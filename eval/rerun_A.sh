#!/bin/bash
# 清空 A 通道记录(保留 B),重跑 A 通道(HyDE+邻接开启)
cd /home/administrator/lemeng-rag
.venv/bin/python - << 'EOF'
import json
p = json.load(open("eval/results/eval60_progress.json"))
p["A"] = {}
json.dump(p, open("eval/results/eval60_progress.json", "w"), ensure_ascii=False, indent=1)
print("A 通道已清空,保留 B 通道", len(p["B"]), "题")
EOF
.venv/bin/python -u eval/eval_paired_60.py --pipelines A > /tmp/eval60_A_v2.log 2>&1
echo A-DONE
tail -3 /tmp/eval60_A_v2.log
