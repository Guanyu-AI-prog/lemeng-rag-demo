"""意图分流:关键词快速路径 + LLM 兜底分类"""
import json
import logging
import re
from typing import Dict, List, Optional

from agent.llm import chat
from agent.prompts import ROUTER_PROMPT, ROUTER_WITH_HISTORY_PROMPT

logger = logging.getLogger(__name__)


def _format_history(history: List[Dict[str, str]]) -> str:
    lines = []
    for h in history[-6:]:
        role = {"user": "用户", "assistant": "助手"}.get(h.get("role", ""), h.get("role", ""))
        lines.append(f"{role}: {h.get('content', '')}")
    return "\n".join(lines)

# 关键词命中即分流(高置信),否则交给 LLM 分类
_TALK_KW = ["话术", "怎么回复", "怎么聊", "怎么谈", "如何沟通", "怎么沟通", "说服",
            "转化", "推单", "逼单", "邀约", "家长问", "回复家长", "谈单", "销售"]
_SCRIPT_KW = ["拍摄脚本", "脚本", "短视频", "视频文案", "抖音", "视频号", "口播",
              "分镜", "朋友圈文案", "选题", "出镜", "拍一条", "拍个视频"]
_COMPLEX_KW = ["对比", "区别", "差异", "怎么选", "选哪个", "哪个好", "规划",
               "方案", "路径", "几岁", "阶段"]


def classify(query: str, use_llm: bool = True,
             history: Optional[List[Dict[str, str]]] = None) -> str:
    """返回 faq / talk / script / complex"""
    if any(kw in query for kw in _SCRIPT_KW):
        return "script"
    if any(kw in query for kw in _TALK_KW):
        return "talk"

    # 复杂判断:多实体/多问句倾向 complex
    numbers = re.findall(r"[\u4e00-\u9fff]?\d+", query)
    if any(kw in query for kw in _COMPLEX_KW) and len(numbers) >= 2:
        return "complex"

    if not use_llm:
        return "faq"

    try:
        if history:
            prompt = ROUTER_WITH_HISTORY_PROMPT.format(
                history=_format_history(history), query=query)
        else:
            prompt = ROUTER_PROMPT.format(query=query)
        out = chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=60,
        )
        data = json.loads(re.search(r"\{.*\}", out["content"], re.DOTALL).group())
        route = data.get("type", "faq")
        return route if route in ("faq", "talk", "script", "complex") else "faq"
    except Exception as e:
        logger.warning("LLM 分流失败,默认 faq: %s", e)
        return "faq"
