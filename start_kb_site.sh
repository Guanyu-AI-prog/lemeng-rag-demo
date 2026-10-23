#!/bin/bash
# kb-site 静态站 + AI 后端(8866)启动(幂等:已运行则跳过)
cd /home/administrator/lemeng-rag
if curl -s -m 3 http://localhost:8866/health > /dev/null 2>&1; then
    echo "8866 已在运行"
    exit 0
fi
for pid in $(pgrep -f 'kb-site/server.py'); do
    kill "$pid" 2>/dev/null
done
sleep 1
unset KB_URL_PREFIX   # 本地根路径部署
setsid .venv/bin/python "/mnt/c/Users/Administrator/Desktop/hermes/项目代码/kb-site/server.py" \
    > /tmp/kbsite_server.log 2>&1 < /dev/null &
for i in $(seq 1 20); do
    sleep 3
    curl -s -m 3 http://localhost:8866/health > /dev/null 2>&1 && break
done
curl -s http://localhost:8866/health && echo " 8866-UP"
