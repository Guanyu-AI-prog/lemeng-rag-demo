"""验证 config 默认值更新后,当前生效配置与服务状态一致"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config

checks = [
    ("LLM_MODEL", Config.LLM_MODEL, "deepseek-chat"),
    ("EMBED_BACKEND", Config.EMBED_BACKEND, "api"),
    ("EMBED_MODEL", Config.EMBED_MODEL, "BAAI/bge-large-zh-v1.5"),
    ("EMBED_DIM", str(Config.EMBED_DIM), "1024"),
    ("RERANK_BACKEND", Config.RERANK_BACKEND, "api"),
    ("RERANK_MODEL", Config.RERANK_MODEL, "BAAI/bge-reranker-v2-m3"),
    ("HYDE_ENABLED", str(Config.HYDE_ENABLED), "True"),
    ("NEIGHBOR_EXPAND", str(Config.NEIGHBOR_EXPAND), "True"),
]
ok = True
for name, actual, want in checks:
    mark = "✅" if str(actual) == want else "❌"
    if str(actual) != want:
        ok = False
    print(f"{mark} {name} = {actual}")

print("\n" + ("全部一致,配置无误" if ok else "存在不一致,需检查"))
