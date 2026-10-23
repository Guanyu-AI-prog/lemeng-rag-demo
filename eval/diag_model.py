"""对比测试:deepseek-v4-flash(思考) vs deepseek-chat(非思考?)用同样的复杂 prompt"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from openai import OpenAI

client = OpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_API_BASE, timeout=300)

prompt = """你是新媒体内容策划。为主题"少儿编程试听课招生"写一条30秒短视频脚本,
输出分镜表格(镜头|画面|口播|字幕|时长),再给发布文案和3个标签。"""

for model in ["deepseek-v4-flash", "deepseek-chat"]:
    print("=" * 60)
    print("模型:", model)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
        )
        msg = resp.choices[0]
        print("finish_reason:", msg.finish_reason, "| usage:", resp.usage.completion_tokens,
              "tokens | reasoning:", resp.usage.completion_tokens_details.reasoning_tokens)
        print("content 长度:", len(msg.message.content or ""))
        print("content 前150:", (msg.message.content or "")[:150].replace("\n", " "))
    except Exception as e:
        print("调用失败:", str(e)[:200])
