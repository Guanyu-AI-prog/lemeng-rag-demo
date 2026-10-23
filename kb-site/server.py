"""
星芽知识库 LLM Wiki 检索后端
- 加载所有知识页面
- 关键词搜索 + DeepSeek V4 Flash 生成答案
"""
import os, re, json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx

app = FastAPI(title="星芽知识库 · AI检索")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 加载知识库 ──────────────────────────────────────────

# 知识库目录：默认项目内 docs/（与 MkDocs 站点内容一致），可用 KB_VAULT 覆盖
VAULT = Path(os.environ.get("KB_VAULT", str(Path(__file__).resolve().parent / "docs")))
# 站点部署前缀（如 /kb），生成的来源链接与之一致；根路径部署留空
URL_PREFIX = os.environ.get("KB_URL_PREFIX", "").rstrip("/")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_KEY:
    # Try reading from key file
    key_file = Path("/tmp/deepseek_key.txt")
    if key_file.exists():
        DEEPSEEK_KEY = key_file.read_text().strip()

if not DEEPSEEK_KEY:
    print("WARNING: No DeepSeek API key found! Set DEEPSEEK_API_KEY env var or /tmp/deepseek_key.txt")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

# ── RAG 后端（lemeng-rag，混合检索+意图分流）──────────────
# 优先调用 RAG 服务；不可用时自动回退到下方内置关键词检索方案
RAG_API_URL = os.environ.get("RAG_API_URL", "http://127.0.0.1:8001").rstrip("/")

def rag_source_to_url(source_rel: str) -> str:
    """RAG 返回的相对路径(如 '🏢企业基础/校区信息.md')转 MkDocs 页面链接,规则与 load_docs 一致"""
    u = (source_rel or "").replace("\\", "/")
    if u.endswith(".md"):
        u = u[:-3]
    if not u or u == "index":
        return f"{URL_PREFIX}/"
    return f"{URL_PREFIX}/{u}/"

class Doc:
    def __init__(self, path: Path, title: str, content: str, url: str):
        self.path = path
        self.title = title
        self.content = content
        self.url = url
        # Build search index: title + headings + content keywords
        self.search_text = f"{title}\n{content}"

docs: list[Doc] = []
doc_by_title: dict[str, Doc] = {}

# 内部管理文档：不进检索库（前端不展示、AI 不引用），后端仍可直接读文件
EXCLUDE_DOCS = {"操作日志.md", "知识库规范.md"}

def load_docs():
    """Load all knowledge pages, skip raw materials"""
    global docs, doc_by_title
    docs.clear()
    doc_by_title.clear()

    for f in sorted(VAULT.rglob("*.md")):
        rel = f.relative_to(VAULT)
        # Skip hidden files, obsidian config
        if any(p.startswith('.') for p in rel.parts):
            continue
        if 'obsidian' in str(rel).lower() or '.trash' in str(rel).lower():
            continue
        # Skip image md files
        if 'image/' in str(rel):
            continue
        # Skip internal management docs
        if rel.name in EXCLUDE_DOCS:
            continue

        try:
            content = f.read_text(encoding='utf-8', errors='ignore')
        except:
            continue

        # Extract title from first # heading or filename
        title = f.stem
        for line in content.split('\n'):
            if line.startswith('# ') and not line.startswith('## '):
                title = line[2:].strip()
                break

        # Build mkdocs URL（含部署前缀，index.md 映射到站点根）
        u = str(rel).replace('\\', '/')
        u = u[:-3] if u.endswith('.md') else u
        if u == 'index':
            u = ''   # MkDocs serves docs/index.md at site root, not /index/
        url = f"{URL_PREFIX}/{u}/" if u else f"{URL_PREFIX}/"

        doc = Doc(f, title, content, url)
        docs.append(doc)
        doc_by_title[title] = doc

    print(f"Loaded {len(docs)} knowledge pages")

load_docs()

# ── 检索 ────────────────────────────────────────────────

def search(query: str, top_k: int = 5) -> list[dict]:
    """Chinese-aware keyword search"""
    q = query.lower().strip()

    # For Chinese: extract meaningful 2-4 char substrings as search terms
    # plus keep the full query for substring matching
    keywords = set()

    # Extract Chinese character sequences (2-4 char n-grams)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]+', q)
    for chunk in chinese_chars:
        keywords.add(chunk)  # full Chinese segment
        # Add bigrams and trigrams
        for i in range(len(chunk) - 1):
            keywords.add(chunk[i:i+2])
        for i in range(len(chunk) - 2):
            keywords.add(chunk[i:i+3])

    # Also extract non-Chinese words
    other_words = re.findall(r'[a-z0-9]+', q)
    keywords.update(other_words)

    # Also add the full query for direct substring matching
    keywords.add(q)

    keywords.discard('')

    if not keywords:
        return []

    scored = []
    for doc in docs:
        text = doc.search_text.lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])

    results = []
    for score, doc in scored[:top_k]:
        # Extract relevant snippet
        text = doc.search_text.lower()
        # Find first match of any keyword for snippet
        first_kw = next((kw for kw in keywords if kw in text), "")
        snippet_start = text.find(first_kw) if first_kw else 0
        snippet_start = max(0, snippet_start - 100)
        snippet = doc.content[max(0, snippet_start):snippet_start + 400].strip()

        results.append({
            "title": doc.title,
            "url": doc.url,
            "snippet": snippet[:300],
            "content": doc.content[:2000],  # for LLM context
        })

    return results

# ── DeepSeek 调用 ────────────────────────────────────────

SYSTEM_PROMPT = """你是星芽少儿编程知识库的AI助手。请根据提供的知识库内容回答用户问题。

规则：
1. 只依据下面提供的【知识库内容】回答，不要编造
2. 如果知识库内容不足以回答问题，明确说"知识库中暂无相关信息"
3. 回答时引用来源（格式：[来源: 页面标题]）
4. 回答简洁专业，面向公司内部成员
5. 用中文回答"""

async def ask_deepseek(question: str, contexts: list[dict]) -> str:
    # Build context block
    ctx_parts = []
    for i, ctx in enumerate(contexts):
        ctx_parts.append(f"[来源{i+1}: {ctx['title']}]\n{ctx['content']}")

    context_block = "\n\n---\n\n".join(ctx_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"【知识库内容】\n\n{context_block}\n\n【用户问题】\n{question}"}
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_KEY}",
                "Content-Type": "application/json",
            },
                json={
                    "model": "deepseek-chat",  # 官方 deepseek-chat（别名已映射 V4-Flash，非思考型）
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1000,
                }
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"DeepSeek API error: {resp.text[:200]}")

    data = resp.json()
    return data["choices"][0]["message"]["content"]

# ── API ──────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    # auto=RAG 自动意图分流；也可手选 faq/talk/script/complex 直通对应通道
    mode: str = "auto"
    session_id: Optional[str] = None
    history: Optional[List[dict]] = None

class AskResponse(BaseModel):
    answer: str
    sources: list[dict]

@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    q = req.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="问题不能为空")

    # 1) 优先走 RAG 服务（向量+BM25+Rerank 混合检索，意图分流，deepseek-chat 生成）
    try:
        payload = {"question": q, "mode": req.mode}
        if req.session_id:
            payload["session_id"] = req.session_id
        if req.history:
            payload["history"] = req.history
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(f"{RAG_API_URL}/ask", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            sources = [
                {
                    "title": s.get("title", ""),
                    "url": rag_source_to_url(s.get("source", "")),
                    "snippet": "",
                }
                for s in data.get("sources", [])
            ]
            return AskResponse(answer=data.get("answer", ""), sources=sources)
        print(f"RAG /ask 非200({resp.status_code})，回退内置检索")
    except Exception as e:
        print(f"RAG 不可用({e})，回退内置检索")

    # 2) 回退：内置关键词检索 + DeepSeek
    results = search(q, top_k=5)

    if not results:
        return AskResponse(
            answer="知识库中暂无与您问题相关的内容。请尝试换个关键词提问。",
            sources=[]
        )

    # Ask DeepSeek
    answer = await ask_deepseek(q, results)

    # Build source list
    sources = [
        {"title": r["title"], "url": r["url"], "snippet": r["snippet"]}
        for r in results
    ]

    return AskResponse(answer=answer, sources=sources)

@app.get("/health")
async def health():
    return {"status": "ok", "docs_loaded": len(docs)}

@app.get("/reload")
async def reload():
    load_docs()
    return {"status": "reloaded", "docs_loaded": len(docs)}

# ── 静态站点（本地一键运行用；服务器上由 nginx 服务静态文件时此挂载不冲突）──
from fastapi.staticfiles import StaticFiles
SITE_DIR = Path(os.environ.get("KB_SITE_DIR", str(Path(__file__).resolve().parent / "site")))
if SITE_DIR.exists():
    # 必须在所有 API 路由之后挂载,否则会遮蔽 /ask /health
    app.mount("/", StaticFiles(directory=str(SITE_DIR), html=True), name="site")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8866)
