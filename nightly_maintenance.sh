#!/bin/bash
# 星芽知识库夜间维护(23:30 cron):三服务守护 + 同步 + 按需重建 + e2e评测 + 日报
cd /home/administrator/lemeng-rag
DATE=$(date '+%Y-%m-%d %H:%M')
ISSUES=""

# ── 0) 服务守护 ──
curl -s -m 5 http://localhost:8001/health > /dev/null 2>&1 || { bash restart.sh > /dev/null 2>&1; ISSUES="$ISSUES [8001被拉起]"; }
curl -s -m 5 http://localhost:8866/health > /dev/null 2>&1 || { bash start_kb_site.sh > /dev/null 2>&1; ISSUES="$ISSUES [8866被拉起]"; }
if ! curl -s -m 5 http://localhost:8086/docs > /dev/null 2>&1; then
    cd /home/administrator/projects/edu-backend
    setsid nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8086 > /tmp/edu8086.log 2>&1 < /dev/null &
    sleep 6
    cd /home/administrator/lemeng-rag
    ISSUES="$ISSUES [8086被拉起]"
fi

# ── 1) 同步知识库 ──
bash sync_data.sh > /dev/null 2>&1
MD_COUNT=$(find data -name '*.md' | wc -l)

# ── 2) 更新判定(上次 125)──
REBUILT="无更新"
if [ "$MD_COUNT" != "125" ]; then
    .venv/bin/python -u ingest/build_index.py --force > /tmp/nightly_rebuild.log 2>&1
    bash restart.sh > /dev/null 2>&1
    bash start_kb_site.sh > /dev/null 2>&1
    REBUILT="已重建"
    ISSUES="$ISSUES [知识库有更新:md=$MD_COUNT]"
fi

CHUNKS=$(curl -s -m 5 http://localhost:8001/health | grep -oE '"chunks":[0-9]+' | grep -oE '[0-9]+')

# ── 3) 真实用户路径回归评测 ──
E2E_OUT=$(.venv/bin/python -u eval/e2e_user_path.py 2>&1)
KB_HIT=$(echo "$E2E_OUT" | grep 'kb-site' | grep -oE '[0-9]+/30' | head -1 | grep -oE '[0-9]+')
EDU_HIT=$(echo "$E2E_OUT" | grep '教务' | grep -oE '[0-9]+/30' | head -1 | grep -oE '[0-9]+')
echo "$E2E_OUT" | grep -q '低于红线' && ISSUES="$ISSUES [e2e低于红线]"

# ── 4) 日报 ──
echo "$DATE | $REBUILT | md=$MD_COUNT | chunks=$CHUNKS | kb-site命中=${KB_HIT:-?}/30 | 教务命中=${EDU_HIT:-?}/30 | 异常:${ISSUES:-无}" >> eval/results/nightly_report.md
echo "NIGHTLY-COMPLETE | md=$MD_COUNT | chunks=$CHUNKS | kb=$KB_HIT edu=$EDU_HIT | $ISSUES"
