"""查询扩展:HyDE(假设答案)生成

对"问法与文档措辞不同"的语义 gap(如"收费吗" vs 文档写"公益"),
让 LLM 先写一段假设性的知识库片段,再用它去检索——语义空间对齐文档而非问题。
原查询永远保留参与检索,Hypothetical 内容只用于匹配、不会进入答案。
"""
import logging
import os

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)

HYDE_PROMPT = """针对下面的用户问题,写一段 60-120 字的"知识库片段":像百科条目一样直接陈述最可能的事实(包含具体的名称、数字、年龄、价格等)。
只输出片段本身,不要解释,不要说"可能"。

【问题】
{query}

【知识库片段】"""

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_API_BASE,
            timeout=30,
            max_retries=1,
        )
    return _client


def hyde_answer(query: str) -> str:
    """生成假设答案片段;失败返回空串(调用方自动退化为单路检索)"""
    try:
        resp = _get_client().chat.completions.create(
            model=Config.LLM_MODEL,
            messages=[{"role": "user", "content": HYDE_PROMPT.format(query=query)}],
            temperature=0.2,
            max_tokens=Config.HYDE_MAX_TOKENS,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text[:400]
    except Exception as e:
        logger.warning("HyDE 生成失败,退化为单路检索: %s", e)
        return ""
