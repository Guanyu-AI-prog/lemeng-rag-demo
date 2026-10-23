"""LLM 客户端:OpenAI 兼容(DeepSeek/GLM 等),带 429 指数退避重试"""
import logging
import random
import time
from typing import List, Dict, Optional

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)

_clients: dict[str, OpenAI] = {}


def _make_client(api_key: str, api_base: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=api_base, timeout=Config.LLM_TIMEOUT, max_retries=0)


def get_client(complex_channel: bool = False) -> OpenAI:
    """complex=True 返回 complex 通道专用客户端(不同模型/端点);未配置则回落主客户端"""
    key_name = "complex" if complex_channel else "main"
    if key_name not in _clients:
        if complex_channel and Config.LLM_MODEL_COMPLEX:
            _clients[key_name] = _make_client(
                Config.LLM_COMPLEX_API_KEY or Config.LLM_API_KEY,
                Config.LLM_COMPLEX_API_BASE or Config.LLM_API_BASE,
            )
        else:
            _clients[key_name] = _make_client(Config.LLM_API_KEY, Config.LLM_API_BASE)
    return _clients[key_name]


def _resolve(model: str, complex_channel: bool) -> str:
    """complex 通道且配置了专用模型时覆盖模型名"""
    if complex_channel and Config.LLM_MODEL_COMPLEX:
        return Config.LLM_MODEL_COMPLEX
    return model


def _is_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "rate limit" in s or "too many requests" in s


def chat(messages: List[Dict[str, str]], temperature: float = None,
         max_tokens: int = None, tools: Optional[list] = None,
         complex_channel: bool = False) -> dict:
    """调用 LLM,返回 message dict。complex_channel=True 走 complex 专用模型/端点。"""
    temperature = Config.LLM_TEMPERATURE if temperature is None else temperature
    max_tokens = max_tokens or Config.LLM_MAX_TOKENS

    last_exc = None
    for attempt in range(4):
        try:
            kwargs = dict(
                model=_resolve(Config.LLM_MODEL, complex_channel),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            resp = get_client(complex_channel).chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            out = {"role": "assistant", "content": msg.content or ""}
            if getattr(msg, "tool_calls", None):
                out["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in msg.tool_calls
                ]
            return out
        except Exception as e:
            last_exc = e
            if _is_rate_limit(e) and attempt < 3:
                wait = min(2 ** attempt, 16) * (0.5 + random.random())
                logger.warning("429 限流,%.1fs 后重试(%d/3)", wait, attempt + 1)
                time.sleep(wait)
            else:
                raise
    raise last_exc


def chat_stream(messages: List[Dict[str, str]], temperature: float = None,
                max_tokens: int = None):
    """流式生成,yield 正文增量。仅用于无工具调用的纯生成场景(faq/talk/script)。"""
    temperature = Config.LLM_TEMPERATURE if temperature is None else temperature
    max_tokens = max_tokens or Config.LLM_MAX_TOKENS

    last_exc = None
    for attempt in range(4):
        try:
            stream = get_client().chat.completions.create(
                model=Config.LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
            return
        except Exception as e:
            last_exc = e
            if _is_rate_limit(e) and attempt < 3:
                wait = min(2 ** attempt, 16) * (0.5 + random.random())
                logger.warning("429 限流,%.1fs 后重试(%d/3)", wait, attempt + 1)
                time.sleep(wait)
            else:
                raise
    raise last_exc
