#!/usr/bin/env python3
"""端到端测试:教务系统(8086) knowledge 通道 → lemeng-rag(8001)"""
import json
import os
import urllib.request

BASE = "http://localhost:8086"
EDU_USER = os.environ.get("EDU_USER", "admin")
EDU_PASS = os.environ.get("EDU_PASS", "")  # 凭据走环境变量/.env,禁止硬编码入库

if not EDU_PASS:
    raise SystemExit("缺少 EDU_PASS 环境变量(教务登录密码)")


def post(path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(data).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


tok = post("/api/auth/login", {"username": EDU_USER, "password": EDU_PASS}).get("access_token")
print("登录 OK")

r = post("/api/ai/chat", {"message": "星芽的课包是怎么收费的?", "mode": "knowledge"}, tok)
print("\n== knowledge 通道回答 ==")
print(r["reply"][:250])
print("来源:", [(s["doc_title"], s["heading"][:20]) for s in r.get("sources", [])][:3])
print("延迟:", r.get("latency_ms"), "ms")
