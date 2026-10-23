"""星芽知识库 RAG — 全局配置"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


class Config:
    # ── 路径 ──
    DATA_DIR = str(BASE_DIR / "data")
    VECTOR_DB_PATH = str(BASE_DIR / "vector_db")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "lemeng_kb")

    # ── Embedding ──
    # backend: local(sentence-transformers,离线) | api(SiliconFlow) | zhipu(智谱 embedding-3)
    EMBED_BACKEND = os.getenv("EMBED_BACKEND", "api")
    EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-large-zh-v1.5")
    EMBED_DIM = _int("EMBED_DIM", 1024)  # bge-large-zh-v1.5=1024(bge-small-zh 已从 SiliconFlow 下架)
    SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
    SILICONFLOW_API_BASE = os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1")
    ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
    ZHIPU_API_BASE = os.getenv("ZHIPU_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
    ZHIPU_EMBED_MODEL = os.getenv("ZHIPU_EMBED_MODEL", "embedding-3")

    # bge 中文模型的官方查询指令,检索时加在 query 前(文档侧不加);
    # 仅对 bge 系列有效,zhipu 等其他后端自动忽略
    BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章:"

    # ── Rerank ──
    # backend: local(CrossEncoder,离线) | api(SiliconFlow) | zhipu(智谱 rerank) | off
    RERANK_BACKEND = os.getenv("RERANK_BACKEND", "api")
    RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    RERANK_TOP_N = _int("RERANK_TOP_N", 5)

    # ── 检索 ──
    VECTOR_TOP_K = _int("VECTOR_TOP_K", 20)
    BM25_TOP_K = _int("BM25_TOP_K", 10)
    RRF_K = 60  # Reciprocal Rank Fusion 常数

    # ── 查询优化(P0)──
    # HyDE:LLM 生成假设答案片段,与原查询双路检索合并(弥合问法与文档措辞的语义 gap)
    HYDE_ENABLED = os.getenv("HYDE_ENABLED", "true").lower() == "true"
    HYDE_WEIGHT = _float("HYDE_WEIGHT", 0.7)   # HyDE 路在 RRF 融合里的权重
    HYDE_MAX_TOKENS = _int("HYDE_MAX_TOKENS", 200)
    # 邻接扩展:命中 chunk 附带同文档相邻 chunk(检索小块、返回大块)
    NEIGHBOR_EXPAND = os.getenv("NEIGHBOR_EXPAND", "true").lower() == "true"
    NEIGHBOR_CHARS = _int("NEIGHBOR_CHARS", 400)  # 每条命中的邻接内容上限

    # ── LLM ──
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1")
    # 只能用 deepseek-chat:deepseek-v4-flash 等思考型模型会把 max_tokens 耗在推理上,正文返回空
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
    # complex 通道(Agent 多步)专用模型:实测 V4-Flash(SiliconFlow)在多轮检索下质量 +1.8 分,
    # 通道对延迟不敏感,慢一点可接受;留空则与主模型一致
    LLM_MODEL_COMPLEX = os.getenv("LLM_MODEL_COMPLEX", "")
    LLM_COMPLEX_API_BASE = os.getenv("LLM_COMPLEX_API_BASE", "")
    LLM_COMPLEX_API_KEY = os.getenv("LLM_COMPLEX_API_KEY", "")
    LLM_TEMPERATURE = _float("LLM_TEMPERATURE", 0.3)
    LLM_MAX_TOKENS = _int("LLM_MAX_TOKENS", 4000)  # 思考型模型会把配额耗在推理上,需留足正文空间
    LLM_TIMEOUT = _int("LLM_TIMEOUT", 90)
    AGENT_MAX_ITERATIONS = _int("AGENT_MAX_ITERATIONS", 4)

    # ── 分类路由 ──
    ROUTER_CONFIDENT_KEYWORDS = True  # 关键词命中即分流,否则 LLM 兜底

    # ── 服务 ──
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = _int("API_PORT", 8001)

    @classmethod
    def validate(cls) -> bool:
        if cls.EMBED_BACKEND == "api" and not cls.SILICONFLOW_API_KEY:
            raise ValueError("EMBED_BACKEND=api 需要设置 SILICONFLOW_API_KEY")
        if cls.EMBED_BACKEND == "zhipu" and not cls.ZHIPU_API_KEY:
            raise ValueError("EMBED_BACKEND=zhipu 需要设置 ZHIPU_API_KEY(需含 embedding 资源包)")
        if not cls.LLM_API_KEY:
            raise ValueError("需要设置 LLM_API_KEY(DeepSeek/GLM 等 OpenAI 兼容 key)")
        if not Path(cls.DATA_DIR).exists():
            raise ValueError(f"知识库目录不存在: {cls.DATA_DIR},先运行 sync_data.sh")
        return True
