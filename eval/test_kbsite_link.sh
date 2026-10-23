#!/bin/bash
# 端到端验证:kb-site server.py(8866) → lemeng-rag(8001) 链路
set -e
cd /home/administrator/lemeng-rag

# 起 kb-site server.py(模拟服务器部署:KB_URL_PREFIX=/kb)
export KB_URL_PREFIX=/kb
export DEEPSEEK_API_KEY=$(grep -E '^DEEPSEEK_API_KEY=' ~/.hermes/.env | head -1 | cut -d= -f2- | tr -d '"')
for pid in $(pgrep -f 'kb-site/server.py' 2>/dev/null); do kill $pid 2>/dev/null || true; done
sleep 1
setsid .venv/bin/python "/mnt/c/Users/Administrator/Desktop/hermes/项目代码/kb-site/server.py" \
    > /tmp/kbsite_server.log 2>&1 < /dev/null &
sleep 8

echo "== server.py health =="
curl -s http://127.0.0.1:8866/health
echo; echo

echo "== /ask 经 RAG 回答(看 sources 是否带 /kb/ 链接)=="
curl -s -X POST http://127.0.0.1:8866/ask \
    -H "Content-Type: application/json" \
    -d '{"question":"星芽的课包是怎么收费的?"}' \
| .venv/bin/python -c "
import json, sys
d = json.load(sys.stdin)
print('answer 前150字:', d['answer'][:150].replace(chr(10),' '))
print('sources:')
for s in d['sources']:
    print('  -', s['title'], '->', s['url'])
"
