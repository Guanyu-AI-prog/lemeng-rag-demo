"""轻量 TTL+LRU 缓存(FAQ 问答结果用)

注意:缓存随进程存活,重建索引后需重启服务(重启即清空)。
"""
import re
import time
from threading import Lock


def normalize_query(q: str) -> str:
    """缓存键归一化:去空白/常见标点、小写——让'课程怎么收费?'和'课程怎么收费'同键"""
    return re.sub(r"[\s，。?!?!、;;:·…\-—/\\'\"]+", "", q).lower()


class TTLCache:
    def __init__(self, max_size: int = 500, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._data: dict[str, tuple[float, object]] = {}
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        with self._lock:
            item = self._data.get(key)
            if not item:
                self.misses += 1
                return None
            ts, value = item
            if time.time() - ts > self.ttl:
                del self._data[key]
                self.misses += 1
                return None
            # LRU 触碰
            self._data.pop(key)
            self._data[key] = item
            self.hits += 1
            return value

    def set(self, key: str, value):
        with self._lock:
            if key in self._data:
                self._data.pop(key)
            elif len(self._data) >= self.max_size:
                self._data.pop(next(iter(self._data)))  # 淘汰最旧
            self._data[key] = (time.time(), value)

    def clear(self):
        with self._lock:
            self._data.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._data),
                "max_size": self.max_size,
                "ttl": self.ttl,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": f"{self.hits / total:.1%}" if total else "-",
            }


faq_cache = TTLCache(max_size=500, ttl=3600)
