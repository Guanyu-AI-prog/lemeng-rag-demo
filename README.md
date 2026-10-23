# lemeng-rag-demo · 四路径混合检索 RAG（脱敏演示版）

> **脱敏演示版**：本仓库是从真实生产项目脱敏而来。四路径 Agent 架构、混合检索实现、评测方法完整保留；知识库正文、真实评测题、业务话术已替换为合成示例（虚构品牌"星芽"）。
>
> 原项目为教育机构内部知识库问答系统，检索层改造自 [rag-agent-system](https://github.com/Guanyu-AI-prog/rag-agent-system)（纯 Python 混合检索）。

## 架构

```
用户提问 ──► 意图分流（router：关键词 + LLM 兜底）
   ├─ faq     事实问答   ─► 混合检索 ─► 生成（带来源引用）
   ├─ talk    营销话术   ─► 多路检索（场景+话术库+卖点） ─► 话术生成
   ├─ script  内容脚本   ─► 多路检索（主题+品牌输出） ─► 脚本生成
   └─ complex 复杂问题   ─► 工具循环（retrieve_knowledge，最多 4 轮）

混合检索 = 向量（1024 维）∥ BM25（jieba + 领域词表）→ RRF 融合 → Rerank（可关）
多轮会话 = session 记忆（TTL 1h）+ LLM 查询改写（代词消解）+ 历史注入生成
```

关键工程点：

- **标题感知切分**：每个 chunk 前缀带「文档标题｜小节路径」，表格整块不拆
- **Embedding/Rerank 多后端可切**（local / API / 第三方），LLM 用 OpenAI 兼容接口
- **Rerank 失败自动降级**：返回未重排文档，不让整个查询挂掉
- **faq 热点缓存**：TTL 1h，缓存命中秒回

## 快速开始

```bash
cp .env.example .env          # 填 LLM_API_KEY / EMBEDDING 配置
python -m venv .venv && .venv/bin/pip install -r requirements.txt
python ingest/build_index.py  # 用示例文档构建索引
python -m uvicorn api.main:app --port 8001
```

## 接口

| 端点 | 说明 |
|------|------|
| `POST /ask` | `{question, mode: auto/faq/talk/script/complex, session_id?, history?}` 统一问答 |
| `POST /ask/stream` | SSE 流式：`meta`（路由+来源）→ `delta*` → `done` |
| `POST /retrieve` | `{query, category?, top_k?}` 纯检索（不生成） |
| `GET /health` | 索引状态 + 缓存 + 会话统计 |

## 评测方法（可复现）

`eval/` 下是配对评测流水线：`sample_questions.py`（12 题合成示例，含单点/对比/计算/流程/边界 5 种题型）→ 检索 → 生成 → 五维打分（召回/完整/准确/幻觉控制/耗时）。

原生产环境 120 题评测均值 90.55；talk 路径流式改造后首字 4.0s（原 36-43s 干等）。

## 给 AI Agent 的工作指令

见 [AGENTS.md](AGENTS.md)：硬性约定（换 embedding 必须重建索引、bge 截断、faq 缓存语义等）与代码结构说明。

## License

MIT
