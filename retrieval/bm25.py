"""BM25 关键词检索(jieba 分词,带星芽领域词表)"""
import logging
from typing import List

import jieba
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# 领域词加入词表,避免被切碎(检索 "430课后"、"CSP-J" 这类词时更准)
DOMAIN_WORDS = [
    "星芽", "小星芽", "少儿编程", "Scratch", "Python", "C++", "信奥", "信息学奥赛",
    "CSP-J", "CSP-S", "GESP", "蓝桥杯", "NOIP", "白名单赛事", "科创校队", "青少宫",
    "430课后", "课后服务", "试听课", "体验课", "续费", "续报", "课酬", "升学规划",
    "学业规划师", "家长会", "会销", "转介绍", "获客", "话术", "卖点", "竞品",
    "机器人课", "乐高", "早期结构", "算法思维", "图形化编程", "考级", "赛事",
    "橙分期", "全额预存", "虚实造物营", "正价营", "AI营", "L2", "L3",
]

for _w in DOMAIN_WORDS:
    jieba.add_word(_w, freq=1000)

_STOP_WORDS = set("的了在是我有和就不人都一上也很是到说要去做让把被将这那个你我会着没有看 good".split()) | {
    "什么", "怎么", "为什么", "如何", "哪个", "多少", "可以", "应该", "需要", "请问",
    "一下", "一些", "这个", "那个", "还是", "或者", "以及", "如果", "所以", "因为",
}


def tokenize(text: str) -> List[str]:
    return [t.strip().lower() for t in jieba.cut(text)
            if t.strip() and t.strip() not in _STOP_WORDS and not t.strip().isspace()]


class BM25Index:
    def __init__(self, records: List[dict]):
        """records: [{id, text, metadata}](与 Chroma 库同源)"""
        logger.info("构建 BM25 索引: %d 个文档", len(records))
        self.records = records
        corpus = [r["text"] for r in records]
        self._bm25 = BM25Okapi([tokenize(c) for c in corpus]) if corpus else None

    def search(self, query: str, top_k: int = 10) -> List[dict]:
        """返回命中记录(带 metadata),按 BM25 降序,分数为 0 的丢弃"""
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        pairs = [(i, s) for i, s in enumerate(scores) if s > 0]
        pairs.sort(key=lambda x: x[1], reverse=True)
        return [
            {"text": self.records[i]["text"],
             "metadata": self.records[i]["metadata"],
             "bm25_score": s}
            for i, s in pairs[:top_k]
        ]
