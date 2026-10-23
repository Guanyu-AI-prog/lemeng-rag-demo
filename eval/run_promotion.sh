#!/bin/bash
# 晋级全量:V4-Flash 补全 120 题(A+B)+ GLM-5.3 补 B 通道 31-120
cd /home/administrator/lemeng-rag
QIDS_C=$(seq -s, 31 120)

echo "===== 1/2 DeepSeek-V4-Flash 全量(31-120 A+B)====="
.venv/bin/python -u eval/eval_paired_60.py \
    --llm "deepseek-ai/DeepSeek-V4-Flash" --qids "$QIDS_C" \
    > /tmp/eval_v4flash_full.log 2>&1
tail -3 /tmp/eval_v4flash_full.log

echo "===== 2/2 GLM-5.3 B通道(31-120)====="
.venv/bin/python -u eval/eval_paired_60.py \
    --llm "zai-org/GLM-5.3" --qids "$QIDS_C" --pipelines B \
    > /tmp/eval_glm_full.log 2>&1
tail -3 /tmp/eval_glm_full.log

echo "PROMOTION-DONE"
