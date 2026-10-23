# -*- coding: utf-8 -*-
"""
把 PDF 转换稿 Markdown（含「## 第N页」分页标记、页眉、页码、碎表格、断行段落）
重构为结构化 Markdown，供 MkDocs Material 渲染出带目录/层级/表格的漂亮页面。

用法: python convert_pdf_md.py <输入.md> [输出.md] [--dry-run]
"""
import re
import sys
import shutil
from pathlib import Path

# ── 正则 ──────────────────────────────────────────────
RE_PAGE = re.compile(r'^##\s*第\s*(\d+)\s*页\s*$')
RE_PAGE_NUM = re.compile(r'^\s*(\d{1,3})\s*$')          # 孤立页码行
RE_PIAN = re.compile(r'^第[一二三四五六七八九十百]+篇\s*(\S.*)$')        # 第X篇
RE_ZHANG = re.compile(r'^第[一二三四五六七八九十百]+章\s*(\S.*)$')       # 第X章
RE_QIANYAN = re.compile(r'^前言\s*(\S.*)$')
RE_LEMENGPIAN = re.compile(r'^星芽篇\s*(\S.*)$')
RE_XU_PIAN = re.compile(r'^((?![本这上下])[\u4e00-\u9fff]{2,4}篇)[：:]\s*(\S.*)$')  # 认知篇：… / 政策篇：…（无"第"字）
RE_FULU = re.compile(r'^附录([A-Z])\.?\s*(\S.*)$')       # 附录A. xxx
RE_FULU_BARE = re.compile(r'^附录\s*$')                   # 独立"附录"行
RE_JIE = re.compile(r'^(\d{1,2})\.(\d{1,2})[\s　]*([\u4e00-\u9fff（(].*)$')  # 20.1 英语：…（须后跟汉字）
RE_BIAO = re.compile(r'^表([0-9A-Z]+)-(\d+)\s*(\S.*)$')  # 表20-1 / 表A-1
RE_REFERENCE = re.compile(r'^数据来源与参考资料\s*$')     # 数据来源与参考资料
RE_FULU_JIE = re.compile(r'^([A-Z])\.(\d{1,2})\s*(\S.*)$')  # L.1 xxx（附录小节）
RE_NUM_ZHANG = re.compile(r'^(\d{1,2})[\s　]*([\u4e00-\u9fff][^：:]*[：:].*)$')  # 28星芽闭环总览：… / 1 为什么规划：…（数字直接接汉字标题）
RE_NUM_ITEM = re.compile(r'^\d{1,2}\. ')                 # 参考文献 "1. xxx"

# 标题行判定（用于表格边界 / 段落边界）
def is_heading(line: str) -> bool:
    s = line.strip()
    if re.match(r'^#{1,6}\s+\S', s):      # 已是 markdown 标题
        return True
    return bool(RE_PIAN.match(s) or RE_ZHANG.match(s) or RE_QIANYAN.match(s)
                or RE_LEMENGPIAN.match(s) or RE_FULU.match(s)
                or RE_FULU_BARE.match(s) or RE_JIE.match(s) or RE_BIAO.match(s)
                or RE_REFERENCE.match(s) or RE_FULU_JIE.match(s))

# 中文标点
PUNC_END = '。！？"”’'
PUNC_ALL = '。，；：！？"”’、'


def strip_page_headers(pages):
    """pages: list of (page_no, list_of_lines)。删除每页的页眉标题行 + 页码行。"""
    cleaned = []
    for _, lines in pages:
        block = [l.rstrip() for l in lines]
        # 去掉块首空行
        while block and not block[0].strip():
            block.pop(0)
        if not block:
            continue
        first = block[0].strip()
        # 情况1: 页眉标题行 + 页码行（如 第二十章… / 37 / 1为什么规划：… / 8）
        if len(block) >= 2:
            second = block[1].strip()
            if (RE_PIAN.match(first) or RE_ZHANG.match(first) or RE_QIANYAN.match(first)
                    or RE_LEMENGPIAN.match(first) or RE_FULU.match(first)
                    or RE_FULU_BARE.match(first) or RE_REFERENCE.match(first)
                    or RE_NUM_ZHANG.match(first)) and RE_PAGE_NUM.match(second):
                block = block[2:]
        # 情况2: 删除块内所有孤立页码行（≤3 位数字），目录页页码一并删除
        block = [l for l in block if not (RE_PAGE_NUM.match(l.strip()) and len(l.strip()) <= 3)]
        cleaned.extend(block)
    return cleaned


def detect_toc(cleaned):
    """把目录页（'目 录' ~ '电子版目录可点击条目直接跳转对应章节。'）转成列表。
    返回 (新行列表, 是否处理过)。"""
    out = []
    i = 0
    n = len(cleaned)
    in_toc = False
    toc_entries = []          # 收集 (标题行, 页码)
    pending = None            # 当前未定页码的目录条目
    seen_toc_start = False
    while i < n:
        line = cleaned[i].strip()
        if line == '目 录' or line == '目录':
            in_toc = True
            seen_toc_start = True
            i += 1
            continue
        if in_toc and '电子版目录可点击条目直接跳转对应章节' in line:
            in_toc = False
            out.extend(format_toc(toc_entries))
            out.append(line)
            i += 1
            continue
        if in_toc:
            # 目录条目
            if (RE_PIAN.match(line) or RE_ZHANG.match(line) or RE_QIANYAN.match(line)
                    or RE_LEMENGPIAN.match(line) or RE_FULU.match(line)
                    or RE_FULU_BARE.match(line) or RE_JIE.match(line)
                    or line.startswith('数据来源与参考资料')):
                if pending:
                    toc_entries.append((pending, None))
                pending = line
            elif RE_PAGE_NUM.match(line) and pending:
                toc_entries.append((pending, line))
                pending = None
            # 其他行（如空行、'前言 2026升学新格局：…' 无页码）忽略，延续 pending
            i += 1
            continue
        out.append(cleaned[i])
        i += 1
    if pending:
        toc_entries.append((pending, None))
    if seen_toc_start and not in_toc:
        pass
    return out


def format_toc(entries):
    """目录条目 → markdown 列表"""
    res = []
    for title, page in entries:
        suffix = f" …… 第{page}页" if page else ""
        # 分组标题（篇/附录裸标题）加粗
        if RE_PIAN.match(title) or RE_FULU_BARE.match(title) or title.startswith('数据来源与参考资料'):
            res.append(f"\n- **{title}**{suffix}")
        elif RE_ZHANG.match(title) or RE_JIE.match(title) or RE_FULU.match(title):
            res.append(f"- {title}{suffix}")
        else:
            res.append(f"- {title}{suffix}")
    return res


def collect_table(cleaned, start):
    """从表标题行开始收集表格区域，返回 (表标题行, 表格数据行列表, 下一个下标)。
    边界：空行跳过（页边界残留）；遇到章/节标题、下一个表标题、附录标题、长正文段（>40且含标点）结束。
    注意：不使用 RE_PIAN / RE_QIANYAN / RE_LEMENGPIAN 作边界——表格单元格内也可能以"前言""第一篇"开头。"""
    n = len(cleaned)
    rows = []
    i = start + 1
    while i < n:
        line = cleaned[i].strip()
        if not line:
            i += 1
            continue
        if RE_ZHANG.match(line) or RE_JIE.match(line) or RE_BIAO.match(line) or RE_FULU.match(line) or RE_FULU_BARE.match(line) or RE_FULU_JIE.match(line):
            break
        # 长正文段（>60 且含中文标点）→ 表格结束（表单元格行一般 ≤46 字符）
        if len(line) > 60 and any(c in PUNC_ALL for c in line):
            break
        rows.append(cleaned[i])
        i += 1
    return cleaned[start], rows, i


def rebuild_table(title_line, rows):
    """把碎表格输出为可靠的「单元格列表」：
       - 每个短行（≤16字符、不含；，。：）= 一个列表项（表格单元格）
       - 极短续行（≤2字符）并入前一项（修复 PDF 截断如「拼读教材」的「材」）
       - 长行 = 独立列表项
    内容 100% 保留、顺序正确、绝不错乱；比碎文本清晰可读。
    """
    items = []          # 列表项文本
    for r in rows:
        s = r.strip()
        if not s:
            continue
        is_short = len(s) <= 16 and not any(c in '；，。：' for c in s)
        if is_short:
            # 续行并入: 单字截断（握/材/考/播），或 2 字符闭合括号续行（级））
            if (len(s) == 1 or (len(s) == 2 and any(b in s for b in '）】」』》'))) and items:
                items[-1] += s
            else:
                items.append(s)
        else:
            items.append(s)
    if not items:
        return f"**{title_line.strip()}**\n\n_（表格内容见原文 PDF）_"
    # 长行且语义完整（含句末标点或逗号收尾）→ 作为独立段落输出（正文说明）；
    # 其余为表格单元格列表项
    out = [f"**{title_line.strip()}**", ""]
    for it in items:
        if len(it) > 45 and (any(c in '。！？' for c in it) or it.endswith('，')):
            out.append(it)
        else:
            out.append(f"- {it}")
    return '\n'.join(out)


def merge_paragraphs(lines):
    """把正文连续行合并为段落（表格区域已提前抽出，这里只处理普通行）。"""
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].rstrip()
        s = line.strip()
        if not s:
            out.append('')
            i += 1
            continue
        # 标题/表格标题/列表项/参考文献条目 直接输出
        if is_heading(s) or s.startswith('- ') or s.startswith('* ') or re.match(r'^\*\*表\d+-\d+', s) or RE_NUM_ITEM.match(s):
            out.append(s)
            i += 1
            continue
        # 正文: 收集连续行直到段落结束
        buf = [s]
        i += 1
        while i < n:
            nxt = lines[i].rstrip().strip()
            if not nxt:
                break
            if is_heading(nxt) or nxt.startswith('- ') or nxt.startswith('* ') or re.match(r'^\*\*表\d+-\d+', nxt):
                break
            # 短行（表格单元格残留）独立成行，不并入段落
            if len(nxt) <= 16 and not any(c in '；，。：' for c in nxt):
                break
            buf.append(nxt)
            i += 1
        # 合并: 判断是否以句末标点结束（最后一行决定）
        text = ''.join(buf)
        out.append(text)
    return out


def infer_title(in_path: Path, raw_lines) -> str:
    """推断文档 H1：优先取原文件首个 markdown H1，否则从文件名清洗。"""
    for l in raw_lines:
        m = re.match(r'^#\s+(.+)', l)
        if m:
            return m.group(1).strip()
    stem = Path(in_path).stem
    stem = re.sub(r'（[^）]*）', '', stem)          # 去括号内容
    for tail in ['_副本', '_星芽教育', '_2026', '_2025']:
        stem = stem.replace(tail, '')
    stem = re.sub(r'[\s_]+$', '', stem)
    stem = stem.replace('_', ' ')
    return stem.strip()


def convert(in_path, out_path):
    raw = Path(in_path).read_text(encoding='utf-8')
    lines = raw.split('\n')

    # ── Phase 1: 分页块 ──
    pages = []
    cur_pg, cur_lines = None, []
    for line in lines:
        m = RE_PAGE.match(line.strip())
        if m:
            if cur_pg is not None:
                pages.append((cur_pg, cur_lines))
            cur_pg = int(m.group(1))
            cur_lines = []
        else:
            if cur_pg is not None:
                cur_lines.append(line)
    if cur_pg is not None:
        pages.append((cur_pg, cur_lines))

    if not pages:
        # 没有分页标记 → 原样返回
        Path(out_path).write_text(raw, encoding='utf-8')
        return False

    # 封面（第1页）与版权页（第2页）→ 引用块；其余页正常处理
    frontmatter = []
    body_pages = pages
    if pages and pages[0][0] == 1:
        frontmatter.extend(pages[0][1])
        body_pages = pages[1:]
    if body_pages and body_pages[0][0] == 2:
        frontmatter.extend(body_pages[0][1])
        body_pages = body_pages[1:]

    cleaned = strip_page_headers(body_pages)

    # ── Phase 2: 目录页 ──
    cleaned = detect_toc(cleaned)

    # ── Phase 3+4: 标题提升 + 表格 ──
    result = []
    i = 0
    n = len(cleaned)
    while i < n:
        line = cleaned[i].rstrip()
        s = line.strip()
        if not s:
            i += 1
            continue
        m = RE_PIAN.match(s)
        if m:
            result.append(f"## 第{RE_PIAN.match(s).group(0).split('篇')[0][1:]}篇　{m.group(1)}")
            i += 1
            continue
        m = RE_ZHANG.match(s)
        if m:
            num = RE_ZHANG.match(s).group(0)[:RE_ZHANG.match(s).group(0).find('章')+1]
            result.append(f"### {num}　{m.group(1)}")
            i += 1
            continue
        m = RE_QIANYAN.match(s)
        if m:
            result.append(f"### 前言　{m.group(1)}")
            i += 1
            continue
        m = RE_LEMENGPIAN.match(s)
        if m:
            result.append(f"## 星芽篇　{m.group(1)}")
            i += 1
            continue
        m = RE_XU_PIAN.match(s)
        if m:
            result.append(f"## {m.group(1)[:-1]}　{m.group(2)}")
            i += 1
            continue
        m = RE_FULU.match(s)
        if m:
            result.append(f"## 附录{m.group(1)}　{m.group(2)}")
            i += 1
            continue
        if RE_FULU_BARE.match(s):
            result.append("## 附录")
            i += 1
            continue
        m = RE_JIE.match(s)
        if m:
            result.append(f"#### {m.group(1)}.{m.group(2)}　{m.group(3)}")
            i += 1
            continue
        m = RE_REFERENCE.match(s)
        if m:
            result.append("## 数据来源与参考资料")
            i += 1
            continue
        if re.match(r'^本书使用指南\s*$', s):
            result.append("### 本书使用指南")
            i += 1
            continue
        m = RE_FULU_JIE.match(s)
        if m:
            result.append(f"#### {m.group(1)}.{m.group(2)}　{m.group(3)}")
            i += 1
            continue
        m = RE_NUM_ZHANG.match(s)
        if m:
            result.append(f"### {m.group(1)}　{m.group(2)}")
            i += 1
            continue
        m = RE_BIAO.match(s)
        if m:
            title, rows, nxt = collect_table(cleaned, i)
            result.extend(rebuild_table(title, rows).split('\n'))
            i = nxt
            continue
        # 普通行
        result.append(line)
        i += 1

    # ── Phase 5: 段落合并 ──
    merged = merge_paragraphs(result)

    # 加 H1 标题
    final = []
    final.append(f"# {infer_title(in_path, lines)}")
    final.append("")
    # 封面/版权 → 引用块
    if frontmatter:
        fm = [l.rstrip() for l in frontmatter if l.strip()]
        # 去掉封面里的孤立页码与页眉残行
        fm = [l for l in fm if not (RE_PAGE_NUM.match(l.strip()) and len(l.strip()) <= 3)]
        if fm:
            final.append("> " + "\n> ".join(fm))
            final.append("")
    final.append("---")
    final.append("")
    final.extend(merged)

    out_text = '\n'.join(final) + '\n'
    Path(out_path).write_text(out_text, encoding='utf-8')
    return True


if __name__ == '__main__':
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src
    dry = '--dry-run' in sys.argv
    if not dry and src.resolve() == dst.resolve():
        bak = str(src) + '.orig.bak'
        if not Path(bak).exists():   # 已有备份则不覆盖（保留最原始的 PDF 转换稿）
            shutil.copy2(src, bak)
    changed = convert(src, dst)
    print(f"{'DRY-RUN ' if dry else ''}转换完成: {src.name} -> {dst.name} (结构化: {changed})")
