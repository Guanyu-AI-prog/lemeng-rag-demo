#!/bin/bash
# 一键启动本地知识库:RAG(8001) + kb-site 站点与AI后端(8866)
cd /home/administrator/lemeng-rag

echo "== 1. RAG 服务(8001)=="
if curl -s -m 3 http://localhost:8001/health > /dev/null 2>&1; then
    echo "已在运行: $(curl -s http://localhost:8001/health)"
else
    bash restart.sh
fi

echo
echo "== 2. kb-site 站点(8866)=="
for pid in $(pgrep -f 'kb-site/server.py'); do
    kill "$pid" 2>/dev/null
done
sleep 1
unset KB_URL_PREFIX   # 本地根路径部署,来源链接为 / 开头
setsid .venv/bin/python "/mnt/c/Users/Administrator/Desktop/hermes/项目代码/kb-site/server.py" \
    > /tmp/kbsite_server.log 2>&1 < /dev/null &
echo "等待站点加载(/mnt/c 挂载盘读 135 个 md 稍慢)..."
for i in $(seq 1 20); do
    sleep 3
    if curl -s -m 3 http://localhost:8866/health > /dev/null 2>&1; then
        break
    fi
done
curl -s http://localhost:8866/health
echo

echo
echo "== 3. 验证 =="
echo -n "站点首页: "
curl -s -o /dev/null -w "%{http_code}" http://localhost:8866/
echo
echo -n "AI 后端(经 RAG): "
curl -s -X POST http://localhost:8866/ask -H "Content-Type: application/json" \
    -d '{"question":"星芽有哪些课程?"}' -m 120 | head -c 150
echo
echo
echo "✅ 浏览器访问: http://localhost:8866/  (右下角吉祥物 = 问小星芽)"
