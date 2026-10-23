#!/usr/bin/env python3
"""端到端真实用户路径评测:从两个实际网页入口发问,像真实用户一样

入口1 kb-site:   POST http://localhost:8866/ask          (server.py → lemeng-rag)
入口2 教务系统:  POST http://localhost:8086/api/ai/chat   (登录token, mode=knowledge → lemeng-rag)

用 kb30 锚点 30 题的 key_facts 做答案命中判定(入口级端到端,含服务栈/代理/鉴权)。
输出:每入口 命中数/30、平均延迟、失败题清单;结果可被夜间 cron 直接使用。

用法: python eval/e2e_user_path.py [--limit N]
"""
import argparse
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
sys.path.insert(0, str(BASE_DIR / "eval"))
from sample_questions import KB30_QUESTIONS

KB_ENTRY = "http://localhost:8866"
EDU_ENTRY = "http://localhost:8086"
EDU_USER = os.environ.get("EDU_USER", "admin")
EDU_PASS = os.environ.get("EDU_PASS", "")  # 凭据走环境变量/.env,禁止硬编码入库

THRESHOLD = 24  # 30 题命中红线


def http_json(url, data=None, token=None, timeout=180):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def edu_login():
    if not EDU_PASS:
        raise SystemExit("缺少 EDU_PASS 环境变量(教务登录密码)")
    return http_json(f"{EDU_ENTRY}/api/auth/login",
                     {"username": EDU_USER, "password": EDU_PASS}).get("access_token")


def ask_kb(q):
    t0 = time.time()
    d = http_json(f"{KB_ENTRY}/ask", {"question": q})
    return d.get("answer", ""), time.time() - t0


def ask_edu(q, token):
    t0 = time.time()
    d = http_json(f"{EDU_ENTRY}/api/ai/chat",
                  {"message": q, "mode": "knowledge", "reset": True}, token)
    return d.get("reply", ""), time.time() - t0


def hit_ratio(answer, key_facts):
    if not key_facts:
        return 1.0
    return sum(1 for k in key_facts if k in answer) / len(key_facts)


def run_entry(name, ask_fn, cases):
    hits, fails, latencies, details = 0, [], [], []
    for tc in cases:
        q = tc["question"]
        try:
            answer, sec = ask_fn(q)
            ratio = hit_ratio(answer, tc["key_facts"])
            ok = ratio >= 0.5  # 一半以上关键事实命中算过(与配对评测口径近似)
            hits += ok
            latencies.append(sec)
            details.append({"id": tc["id"], "question": q, "hit_ratio": round(ratio * 100),
                            "ok": ok, "latency": round(sec, 2), "answer": answer})
            if not ok:
                fails.append((tc["id"], round(ratio * 100), q[:24], answer[:40].replace("\n", " ")))
        except Exception as e:
            details.append({"id": tc["id"], "question": q, "hit_ratio": 0, "ok": False,
                            "latency": 0, "answer": f"入口异常: {str(e)[:120]}"})
            fails.append((tc["id"], 0, q[:24], f"入口异常: {str(e)[:80]}"))
        time.sleep(0.5)
    lat = round(statistics.mean(latencies), 1) if latencies else 0
    return {"entry": name, "hits": hits, "total": len(cases),
            "avg_latency": lat, "fails": fails, "details": details}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    cases = KB30_QUESTIONS[: args.limit] if args.limit else KB30_QUESTIONS

    results = []

    # 入口1:kb-site(8866)
    try:
        http_json(f"{KB_ENTRY}/health", timeout=10)
        results.append(run_entry("kb-site(8866)", lambda q: ask_kb(q), cases))
    except Exception as e:
        results.append({"entry": "kb-site(8866)", "hits": 0, "total": len(cases),
                        "avg_latency": 0, "fails": [("ALL", 0, "入口不可达", str(e)[:80])]})

    # 入口2:教务系统(8086,需登录)
    try:
        token = edu_login()
        results.append(run_entry("教务系统(8086)",
                                 lambda q: ask_edu(q, token), cases))
    except Exception as e:
        results.append({"entry": "教务系统(8086)", "hits": 0, "total": len(cases),
                        "avg_latency": 0, "fails": [("ALL", 0, "入口不可达/登录失败", str(e)[:80])]})

    print("=" * 70)
    print("真实用户路径端到端评测(锚点30题,两入口)")
    print("=" * 70)
    for r in results:
        status = "✅" if r["hits"] >= THRESHOLD else "⚠️ 低于红线"
        print(f"{status} {r['entry']}: 命中 {r['hits']}/{r['total']} | 平均延迟 {r['avg_latency']}s")
        for f in r["fails"][:6]:
            print(f"    ✗ [{f[0]}] {f[2]} (命中{f[1]}%) {f[3]}")
        if len(r["fails"]) > 6:
            print(f"    ... 等 {len(r['fails'])} 题")

    # 写 JSON 结果:按日期归档(不覆盖前一天)+ latest 副本(快捷访问)
    date_tag = time.strftime("%Y-%m-%d")
    dest = BASE_DIR / "eval" / "results" / f"e2e_user_path_{time.strftime('%Y%m%d')}.json"
    latest = BASE_DIR / "eval" / "results" / "e2e_user_path_latest.json"
    payload = json.dumps({"time": time.strftime("%Y-%m-%d %H:%M"),
                          "results": results}, ensure_ascii=False, indent=1)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(payload)
    with open(latest, "w", encoding="utf-8") as f:
        f.write(payload)
    print(f"\n结果已保存: {dest}(当日归档,不覆盖此前日期)+ {latest}")


if __name__ == "__main__":
    main()
