from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class CacheEntry:
    """Lightweight cache entry with TTL and access stats.

    Provides fields expected by semantic_cache: created_at, last_accessed,
    access_count, ttl, plus helpers update_access() and is_expired().
    """
    value: Any = None
    ttl: Optional[int] = None
    created_at: float = field(default_factory=lambda: time.time())
    last_accessed: float = field(default_factory=lambda: time.time())
    access_count: int = 0

    def update_access(self) -> None:
        self.last_accessed = time.time()
        try:
            self.access_count += 1
        except Exception:
            self.access_count = 1

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return (self.created_at + int(self.ttl)) < time.time()


class MemoryCache:
    """Simple in-process key/value cache with per-item TTL."""

    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        if entry.is_expired():
            try:
                self._store.pop(key, None)
            except Exception:
                pass
            return None
        entry.update_access()
        return entry.value

    def set(self, key: str, value: Any, ttl_sec: Optional[int] = None) -> None:
        self._store[key] = CacheEntry(value=value, ttl=ttl_sec)

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def clear(self) -> None:
        self._store.clear()


class AdvancedAgenticCache:
    """
    Minimal in-process TTL cache with optional namespacing for agentic features.

    Not multi-process safe; intended to reduce repeat work in a single worker.
    """

    def __init__(self):
        self._store: Dict[Tuple[str, str], Tuple[float, Any]] = {}

    def get(self, namespace: str, key: str) -> Optional[Any]:
        k = (namespace, key)
        item = self._store.get(k)
        if not item:
            return None
        expires_at, value = item
        if expires_at and expires_at < time.time():
            try:
                self._store.pop(k, None)
            except Exception:
                pass
            return None
        return value

    def set(self, namespace: str, key: str, value: Any, ttl_sec: int = 600) -> None:
        try:
            expires_at = time.time() + max(1, int(ttl_sec))
            self._store[(namespace, key)] = (expires_at, value)
        except Exception:
            pass

    def invalidate_prefix(self, namespace: str, prefix: str) -> int:
        to_delete = [k for k in list(self._store.keys()) if k[0] == namespace and k[1].startswith(prefix)]
        for k in to_delete:
            try:
                self._store.pop(k, None)
            except Exception:
                pass
        return len(to_delete)


# Singleton instance
AGENTIC_CACHE = AdvancedAgenticCache()


class _AsyncClearable:
    """Simple async-clear wrapper to satisfy endpoints expecting an async clear()."""

    def __init__(self) -> None:
        self._mem = MemoryCache()

    async def clear(self) -> None:
        self._mem.clear()


class RAGCache:
    """Minimal RAG cache facade for health endpoints.

    Provides a stable API consumed by rag_health without pulling heavy deps.
    Not a full multi-level cache; acts as a lightweight placeholder.
    """

    def __init__(self, enable_multi_level: bool = False) -> None:
        self.enable_multi_level = enable_multi_level
        self._l1 = MemoryCache()
        # Expose an object with async clear() for API compatibility
        self.cache = _AsyncClearable()
        self.warmer = None  # Placeholder; can be wired to a real warmer later

    def get_stats(self) -> Dict[str, Any]:
        """Return lightweight cache stats compatible with rag_health expectations."""
        # Since this is a stub, report zeros and consistent structure
        overall = {
            "hit_rate": 0.0,
            "size": len(getattr(self._l1, "_store", {}))
        }
        l1 = {
            "hit_rate": 0.0,
            "size": len(getattr(self._l1, "_store", {})),
            "evictions": 0,
        }
        l2 = {"hit_rate": 0.0, "size": 0}
        if self.enable_multi_level:
            return {"overall": overall, "l1": l1, "l2": l2}
        return overall
