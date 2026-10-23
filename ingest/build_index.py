"""向量库构建:扫描 data/ → 标题感知切分 → embedding → Chroma 落库

用法:
    python ingest/build_index.py            # 增量(库非空则提示)
    python ingest/build_index.py --force    # 清空重建
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from ingest.markdown_splitter import split_markdown
from retrieval.embedder import Embedder
from retrieval.vector_store import VectorStore


def load_chunks(max_chars: int = 500, min_chars: int = 60):
    from ingest.markdown_splitter import Chunk
    chunks = []
    files = sorted(Path(Config.DATA_DIR).rglob("*.md"))
    print(f"扫描 {len(files)} 个 md 文件")
    for fp in files:
        rel = str(fp.relative_to(Config.DATA_DIR))
        try:
            text = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = fp.read_text(encoding="gb18030", errors="ignore")
        file_chunks = split_markdown(text, rel, max_chars=max_chars, min_chars=min_chars)
        chunks.extend(file_chunks)
    return chunks


def build(force: bool = False) -> int:
    embedder = Embedder()
    store = VectorStore(embedder)

    if store.count() > 0:
        if not force:
            print(f"向量库已有 {store.count()} 条,加 --force 重建")
            return store.count()
        print("清空旧向量库 ...")
        store.client.delete_collection(Config.COLLECTION_NAME)
        store = VectorStore(embedder)

    chunks = load_chunks()
    print(f"切分完成: {len(chunks)} 个 chunk")

    texts = [c.content for c in chunks]
    metadatas = [{
        "source": c.source, "category": c.category, "title": c.title,
        "section": c.section, "tags": c.tags, "chunk_index": i,
    } for i, c in enumerate(chunks)]

    print(f"开始 embedding({embedder.backend}/{embedder.model})...")
    embeddings = embedder.embed_documents(texts)
    store.add(texts, embeddings, metadatas)

    print("=" * 50)
    print(f"构建完成: {store.count()} 条 chunk")
    print(f"向量库: {Config.VECTOR_DB_PATH}")
    print(f"维度: {embedder.dim} | 时间: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 50)
    return store.count()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="星芽知识库向量库构建")
    parser.add_argument("--force", action="store_true", help="清空重建")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--chunk-min", type=int, default=60)
    args = parser.parse_args()
    Config.validate()
    build(force=args.force)
