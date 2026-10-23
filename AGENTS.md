# AGENTS.md — 给 AI Coding Agent 的工作指令

> 面向人介绍/部署文档见 [README.md](README.md)。本文件写给在本仓库工作的 AI agent。
>
> 本仓库为脱敏演示版：四路径 RAG 架构、混合检索与评测方法完整保留；知识库正文、真实评测题、业务话术已替换为合成示例。

## 项目一句话

多路径 RAG 问答系统：意图分流（faq/talk/script/complex）→ 混合检索（向量+BM25+Rerank，RRF 融合）→ LLM 生成。检索层改造自 [rag-agent-system](https://github.com/Guanyu-AI-prog/rag-agent-system)（纯 Python 混合检索）。

## 常用命令

```bash
bash sync_data.sh # 同步知识库 docs/ → data/（含排除规则）
python ingest/build_index.py --force # 重建向量索引
python -m uvicorn api.main:app --port 8001 # 启动服务
python eval/retrieval_demo.py # 典型 case 检索明细演示
python eval/eval_paired_60.py # 配对评测（合成示例题）
bash restart.sh # 重启服务
```

## 硬性约定（违反会坏）

1. **换 embedding 模型或维度 → 必须 `build_index.py --force` 重建**。不同模型向量空间不通用；Rerank 后端切换则无需重建。
2. **bge 系列输入上限 512 token**：`retrieval/embedder.py` 的 `_encode_api` 已截断 500 字符，改动时别丢。
3. `.env` 含真实 key，**永不提交**（已在.gitignore）。
4. **不要手改 `data/`**（构建产物），改 `sync_data.sh` 的排除规则后重新同步。
5. **`chat()` 返回 dict**，取正文用 `chat(messages)["content"]`，不是字符串。
6. **faq 缓存**（`cache.py`）：TTL 1h/500 条，键=归一化问题（去标点空格）；缓存随进程，重建索引后必须重启服务才清空。talk/script/complex 不缓存。
7. **HyDE 默认关闭**（`HYDE_ENABLED=false`）：实测质量持平但 faq 延迟翻倍。如重启用，仅 faq 单轮可开。

## 代码结构

```
config.py 全局配置（env 驱动）；路由/检索/模型全在此调
ingest/markdown_splitter.py 标题感知切分：chunk 前缀带、表格整块不拆（检索质量的关键，慎改）
ingest/build_index.py 入库
retrieval/embedder.py local（SentenceTransformer）/api/智谱 三后端
retrieval/bm25.py jieba+BM25；DOMAIN_WORDS 领域词表（新业务词加这里）
retrieval/reranker.py local/api/智谱/off 四后端，失败自动降级
retrieval/hybrid.py RRF 融合入口 HybridRetriever.retrieve(query, top_k, category)
agent/router.py 分流：关键词快路径 + LLM 兜底（输出 JSON）
agent/agent.py 四路径实现；complex 走 OpenAI 原生 tool_calls 工具循环（勿改回文本解析）
agent/prompts.py 顾问人设/话术/脚本/分流 prompt（业务调优主要改这里；品牌名为虚构示例）
api/main.py FastAPI：/ask /ask/stream /retrieve /health
eval/ 评测与诊断脚本；sample_questions.py 为合成示例题
```

## 已知坑

- `nohup &` 起的服务可能被空闲回收，用 `setsid... < /dev/null &`；`pkill -f` 模式会误杀自身，先 `pgrep` 拿 pid 再 `kill`。
- 中文 JSON 经 curl 传参易引号地狱，测试一律写成 `eval/*.py` 脚本本地跑。
