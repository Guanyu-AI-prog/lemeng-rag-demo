#!/bin/bash
# 干净对照:同索引、deepseek-chat、无 HyDE 的 A 通道 120 题(决定 HyDE 去留)
cd /home/administrator/lemeng-rag/eval/results
cp eval60_progress.json eval60_progress_hyde_on.json
cd /home/administrator/lemeng-rag
.venv/bin/python - << 'EOF'
import json
p = json.load(open("eval/results/eval60_progress.json"))
p["A"] = {}
json.dump(p, open("eval/results/eval60_progress.json", "w"), ensure_ascii=False, indent=1)
print("A 通道已清空(保留 B)")
EOF
HYDE_ENABLED=false .venv/bin/python -u eval/eval_paired_60.py --pipelines A > /tmp/eval_nohyde.log 2>&1
echo NOHYDE-DONE
tail -3 /tmp/eval_nohyde.log
