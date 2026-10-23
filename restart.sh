#!/bin/bash
# 重启 RAG 服务(杀旧进程 + setsid 起新进程 + 健康检查)
cd "$(dirname "$0")"

for pid in $(pgrep -f 'uvicorn api.main'); do
    kill "$pid" 2>/dev/null
done
sleep 2

setsid .venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8001 \
    > server.log 2>&1 < /dev/null &
sleep 28
curl -s http://localhost:8001/health
echo
