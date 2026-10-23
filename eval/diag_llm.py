"""诊断 script 路径 LLM 空返回:看 finish_reason / usage / reasoning_content"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from openai import OpenAI

client = OpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_API_BASE, timeout=180)

resp = client.chat.completions.create(
    model=Config.LLM_MODEL,
    messages=[{"role": "user", "content": "用一句话介绍星芽少儿编程,并给一条30秒招生视频的开场口播。"}],
    temperature=0.3,
    max_tokens=4000,
)
msg = resp.choices[0]
print("finish_reason:", msg.finish_reason)
print("usage:", resp.usage)
content = msg.message.content or ""
print("content 长度:", len(content))
print("content:", content[:300])
rc = getattr(msg.message, "reasoning_content", None)
if rc:
    print("reasoning_content 长度:", len(rc))
    print("reasoning 前200字:", rc[:200])
