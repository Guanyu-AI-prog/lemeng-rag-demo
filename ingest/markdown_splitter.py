"""Markdown 标题感知切分器

针对星芽知识库(手册/话术/表格密集)的切分策略:
1. 剥离 YAML frontmatter,tags 进入 metadata
2. 按标题层级(#..####)切小节,记录标题路径(如 "价格 > 课程价格表")
3. 每个 chunk 文本前缀带上「文档标题｜小节路径」,让向量和 BM25 都吃到标题信号
   —— 这是 eval_kb30 里"价格档位表/禁用词表 chunk 召不回"的直接解法
4. 表格保护:连续表格行不与正文拆散
5. 超长小节按段落递归切,过短小节并入前一块
"""
import re
from dataclasses import dataclass, field

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
_TABLE_LINE_RE = re.compile(r"^\s*\|")

# 一级目录 emoji → 干净分类名
CATEGORY_MAP = {
    "企业基础": "企业基础",
    "客户服务": "客户服务",
    "课程产品": "课程产品",
    "教务运营": "教务运营",
    "品牌输出": "品牌输出",
    "学员规划": "学员规划",
    "原始素材": "原始素材",
}


@dataclass
class Chunk:
    content: str          # 已含标题前缀的最终文本(入库/检索用)
    body: str             # 纯正文(不含前缀)
    source: str = ""      # 相对路径
    category: str = ""    # 一级分类
    title: str = ""       # 文档标题
    section: str = ""     # 小节路径
    tags: str = ""        # frontmatter tags
    extra: dict = field(default_factory=dict)


def _parse_frontmatter(text: str) -> tuple[str, str]:
    """返回 (去掉frontmatter的正文, tags逗号串)"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return text, ""
    block = m.group(1)
    tags = []
    for line in block.splitlines():
        if re.match(r"^\s*tags\s*:", line):
            part = line.split(":", 1)[1]
            tags = [t.strip() for t in re.split(r"[,，]", part) if t.strip()]
            break
    # YAML 列表形式的 tags
    if not tags:
        in_tags = False
        for line in block.splitlines():
            if re.match(r"^\s*tags\s*:\s*$", line):
                in_tags = True
                continue
            if in_tags:
                t = re.match(r"^\s*-\s+(.+)$", line)
                if t:
                    tags.append(t.group(1).strip())
                else:
                    in_tags = False
    return text[m.end():], ",".join(tags)


def _category_of(rel_path: str) -> str:
    first = rel_path.replace("\\", "/").split("/")[0]
    for key, cat in CATEGORY_MAP.items():
        if key in first:
            return cat
    return "其他"


def _split_table_protected(text: str, max_chars: int) -> list[str]:
    """段落级递归切分:表格块整块保留,普通段落按 句号/换行 切"""
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    # 先按空行分段,再把连续表格行聚合为不可拆的表块
    blocks: list[tuple[str, bool]] = []  # (block_text, is_table)
    buf: list[str] = []
    buf_table = False
    for line in text.splitlines():
        is_table = bool(_TABLE_LINE_RE.match(line))
        if buf and is_table != buf_table:
            blocks.append(("\n".join(buf), buf_table))
            buf = []
        buf_table = is_table
        buf.append(line)
    if buf:
        blocks.append(("\n".join(buf), buf_table))

    chunks: list[str] = []
    cur = ""
    for block, is_table in blocks:
        block = block.strip()
        if not block:
            continue
        # 表块超长也整块保留(表格拆了就没意义)
        if is_table:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(block)
            continue
        if len(cur) + len(block) + 2 <= max_chars:
            cur = f"{cur}\n\n{block}" if cur else block
        else:
            if cur:
                chunks.append(cur)
            # 单段仍超长 → 按句子硬切
            while len(block) > max_chars:
                cut = block.rfind("。", 0, max_chars)
                cut = cut if cut > max_chars // 2 else max_chars
                chunks.append(block[: cut + 1])
                block = block[cut + 1:]
            cur = block
    if cur:
        chunks.append(cur)
    return chunks


def split_markdown(text: str, rel_path: str, max_chars: int = 500,
                   min_chars: int = 60) -> list[Chunk]:
    """切分一个 md 文件为 chunk 列表"""
    body_text, tags = _parse_frontmatter(text)
    category = _category_of(rel_path)
    doc_title = ""  # 取第一个 # 标题,没有则用文件名

    # 按标题切小节:每个小节 = (标题路径, 内容)
    sections: list[tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(body_text))
    if not matches:
        sections.append(("", body_text))
    else:
        # 首个标题前的导语
        prelude = body_text[: matches[0].start()].strip()
        if prelude:
            sections.append(("", prelude))
        path: list[str] = []
        for i, m in enumerate(matches):
            level = len(m.group(1))
            heading = m.group(2).strip()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body_text)
            content = body_text[m.end():end].strip()
            path = path[: level - 1]
            path.append(heading)
            if not doc_title and level == 1:
                doc_title = heading
            sections.append((" > ".join(path), content))
    if not doc_title:
        doc_title = rel_path.split("/")[-1].removesuffix(".md")

    # 小节 → chunk
    chunks: list[Chunk] = []
    for sec_path, sec_text in sections:
        if not sec_text:
            continue
        prefix = f"【{doc_title}｜{sec_path}】\n" if sec_path else f"【{doc_title}】\n"
        pieces = _split_table_protected(sec_text, max_chars)
        for j, piece in enumerate(pieces):
            sec_label = sec_path if j == 0 else f"{sec_path}(续{j})"
            p = f"【{doc_title}｜{sec_label}】\n" if sec_path and j > 0 else prefix
            chunks.append(Chunk(
                content=p + piece,
                body=piece,
                source=rel_path,
                category=category,
                title=doc_title,
                section=sec_label,
                tags=tags,
            ))

    # 过短 chunk 并入前一块
    merged: list[Chunk] = []
    for c in chunks:
        if merged and len(c.body) < min_chars:
            prev = merged[-1]
            prev = Chunk(
                content=prev.content + "\n" + c.body,
                body=prev.body + "\n" + c.body,
                source=prev.source,
                category=prev.category,
                title=prev.title,
                section=prev.section,
                tags=prev.tags,
            )
            merged[-1] = prev
        else:
            merged.append(c)
    return merged
