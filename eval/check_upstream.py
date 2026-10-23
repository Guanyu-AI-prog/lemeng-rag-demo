"""对比 GitHub 仓库最新提交与本地快照(15dadf5, 2026-09-03)"""
import json
import urllib.request

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "check"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

commits = get("https://api.github.com/repos/Guanyu-AI-prog/rag-agent-system/commits?per_page=20")
print("== 本地快照之后的提交 ==")
LOCAL_SHA = "15dadf56fa0f428791028553dc794c69a04475a6"
new_commits = []
found_local = False
for c in commits:
    new_commits.append(c)
    if c["sha"] == LOCAL_SHA:
        found_local = True
        break
if not found_local:
    print("(最近20条里没找到本地快照点,以下全部为新提交或列表截断)")

for c in reversed(new_commits):
    marker = "  " if c["sha"] != LOCAL_SHA else "→ "
    msg = c["commit"]["message"].split("\n")[0]
    print(f"{marker}{c['sha'][:7]} {c['commit']['author']['date']} {msg}")

latest = commits[0]["sha"]
print("\n== 最新 tree vs 本地 95 文件 ==")
tree = get(f"https://api.github.com/repos/Guanyu-AI-prog/rag-agent-system/git/trees/{latest}?recursive=1")
gh_files = {t["path"] for t in tree["tree"] if t["type"] == "blob"}
local_files = set()
import os
BASE = "/mnt/d/Z_code/rag-agent-system"
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
    for f in files:
        p = os.path.relpath(os.path.join(root, f), BASE)
        local_files.add(p.replace("\\", "/"))
print("GitHub 文件数:", len(gh_files), "| 本地文件数:", len(local_files))
added = sorted(gh_files - local_files)
removed = sorted(local_files - gh_files)
print("\nGitHub 新增文件:")
for f in added:
    print("  +", f)
if removed:
    print("\nGitHub 已删除文件:")
    for f in removed:
        print("  -", f)
if not added and not removed:
    print("(文件集完全一致)")
