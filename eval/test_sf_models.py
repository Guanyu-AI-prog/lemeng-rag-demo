"""分别测 SiliconFlow 各模型,确定哪些免费可用"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI
import requests
import config

client = OpenAI(api_key=config.Config.SILICONFLOW_API_KEY,
                base_url=config.Config.SILICONFLOW_API_BASE)

MODELS = [
    ("BAAI/bge-large-zh-v1.5", "付费大模型"),
    ("BAAI/bge-m3", "多语言"),
    ("BAAI/bge-small-zh-v1.5", "小模型"),
]
for model, note in MODELS:
    try:
        resp = client.embeddings.create(model=model, input=["测试"])
        print(f"✅ {model}({note}) 可用 | dim={len(resp.data[0].embedding)}")
    except Exception as e:
        print(f"❌ {model}({note}): {str(e)[:100]}")

try:
    resp = requests.post(
        f"{config.Config.SILICONFLOW_API_BASE}/rerank",
        headers={"Authorization": f"Bearer {config.Config.SILICONFLOW_API_KEY}"},
        json={"model": "BAAI/bge-reranker-v2-m3", "query": "课程怎么收费",
              "documents": ["课包档位5680元", "花都两个校区"], "return_documents": False},
        timeout=30,
    )
    if resp.ok:
        results = resp.json()["results"]
        print(f"✅ BAAI/bge-reranker-v2-m3 可用 | top score={results[0]['relevance_score']:.4f} index={results[0]['index']}")
    else:
        print(f"❌ rerank: HTTP {resp.status_code} {resp.text[:120]}")
except Exception as e:
    print(f"❌ rerank: {str(e)[:120]}")
