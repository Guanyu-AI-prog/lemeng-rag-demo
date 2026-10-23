#!/bin/bash
# 多模型锚点筛选:4 个 SiliconFlow 模型 × 锚点30题(A组)× A/B 双通道
cd /home/administrator/lemeng-rag
for m in "deepseek-ai/DeepSeek-V3.2" "Qwen/Qwen3.5-32B" "zai-org/GLM-5.3" "deepseek-ai/DeepSeek-V4-Flash"; do
    echo "========== MODEL: $m =========="
    .venv/bin/python -u eval/eval_paired_60.py --llm "$m" --group A >> /tmp/llm_screen.log 2>&1
    echo "---- $m done, tail:"
    tail -3 /tmp/llm_screen.log
done
echo "ALL-MODELS-DONE"
