# kb-site 前端示例（脱敏版）

MkDocs 站点 + FastAPI 代理后端的源码示例，与 RAG 后端组成完整链路演示。

| 路径 | 说明 |
|---|---|
| `server.py` | FastAPI 代理后端：`/ask` 转发 RAG 服务（`RAG_API_URL`，默认 `127.0.0.1:8001`），失败回退内置关键词检索 |
| `mkdocs.yml` | MkDocs Material 配置 |
| `docs/assets/` | 前端资源：AI 问答面板 `ai-search.js`、自定义样式 |
| `convert_pdf_md.py` | PDF→Markdown 结构化重构脚本 |

> 品牌图、部署脚本、变更记录等内部文件已在脱敏时移除。
