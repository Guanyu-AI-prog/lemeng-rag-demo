#!/bin/bash
# 停 RAG → 测 server.py fallback → 重启 RAG
cd /home/administrator/lemeng-rag

for pid in $(pgrep -f 'uvicorn api.main'); do
    kill "$pid" 2>/dev/null
done
sleep 2
echo "== RAG 状态 =="
curl -s -m 3 http://localhost:8001/health || echo "RAG 已停"

echo; echo "== fallback 测试(server.py 应走内置检索)=="
.venv/bin/python eval/test_fallback.py

echo; echo "== 重启 RAG =="
bash restart.sh
