"""Session-level multi-turn conversation memory (in-process TTL+LRU).

For multi-instance deployments, replace the dict backend with Redis.
"""
import time
from threading import Lock
from typing import Dict, List, Optional


class SessionMemory:
    def __init__(self, max_sessions: int = 10000, ttl: int = 3600, max_turns: int = 20):
        self.max_sessions = max_sessions
        self.ttl = ttl
        self.max_turns = max_turns
        self._data: Dict[str, tuple[float, List[dict]]] = {}
        self._lock = Lock()

    def _evict_expired(self):
        now = time.time()
        expired = [sid for sid, (ts, _) in self._data.items() if now - ts > self.ttl]
        for sid in expired:
            del self._data[sid]

    def get(self, session_id: str) -> List[dict]:
        with self._lock:
            self._evict_expired()
            item = self._data.get(session_id)
            if not item:
                return []
            _, history = item
            # LRU touch
            self._data.pop(session_id)
            self._data[session_id] = (time.time(), history)
            return list(history)

    def append(self, session_id: str, role: str, content: str):
        with self._lock:
            self._evict_expired()
            item = self._data.get(session_id)
            history = list(item[1]) if item else []
            history.append({"role": role, "content": content})
            max_messages = self.max_turns * 2
            if len(history) > max_messages:
                history = history[-max_messages:]
            if len(self._data) >= self.max_sessions and session_id not in self._data:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[session_id] = (time.time(), history)

    def set(self, session_id: str, history: List[dict]):
        with self._lock:
            self._evict_expired()
            max_messages = self.max_turns * 2
            if len(history) > max_messages:
                history = history[-max_messages:]
            if len(self._data) >= self.max_sessions and session_id not in self._data:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[session_id] = (time.time(), list(history))

    def clear(self, session_id: str):
        with self._lock:
            self._data.pop(session_id, None)

    def clear_all(self):
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        with self._lock:
            self._evict_expired()
            return {
                "sessions": len(self._data),
                "max_sessions": self.max_sessions,
                "ttl": self.ttl,
                "max_turns": self.max_turns,
            }


session_memory = SessionMemory()
