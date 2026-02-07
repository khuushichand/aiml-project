from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """Lightweight cache entry with TTL and access stats.

    Provides fields expected by semantic_cache: created_at, last_accessed,
    access_count, ttl, plus helpers update_access() and is_expired().
    """
    value: Any = None
    ttl: int | None = None
    created_at: float = field(default_factory=lambda: time.time())
    last_accessed: float = field(default_factory=lambda: time.time())
    access_count: int = 0

    def update_access(self) -> None:
        self.last_accessed = time.time()
        try:
            self.access_count += 1
        except TypeError:
            self.access_count = 1

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return (self.created_at + int(self.ttl)) < time.time()


class MemoryCache:
    """Simple in-process key/value cache with per-item TTL."""

    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        if entry.is_expired():
            with contextlib.suppress(KeyError, TypeError):
                self._store.pop(key, None)
            return None
        entry.update_access()
        return entry.value

    def set(self, key: str, value: Any, ttl_sec: int | None = None) -> None:
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
        self._store: dict[tuple[str, str], tuple[float, Any]] = {}

    def get(self, namespace: str, key: str) -> Any | None:
        k = (namespace, key)
        item = self._store.get(k)
        if not item:
            return None
        expires_at, value = item
        if expires_at and expires_at < time.time():
            with contextlib.suppress(KeyError, TypeError):
                self._store.pop(k, None)
            return None
        return value

    def set(self, namespace: str, key: str, value: Any, ttl_sec: int = 600) -> None:
        try:
            expires_at = time.time() + max(1, int(ttl_sec))
            self._store[(namespace, key)] = (expires_at, value)
        except (TypeError, ValueError):
            pass

    def invalidate_prefix(self, namespace: str, prefix: str) -> int:
        to_delete = [k for k in list(self._store.keys()) if k[0] == namespace and k[1].startswith(prefix)]
        for k in to_delete:
            with contextlib.suppress(KeyError, TypeError):
                self._store.pop(k, None)
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
    """RAG cache facade for health endpoints.

    Delegates to a real SemanticCache when one has been registered via
    ``register_semantic_cache()``. Falls back to stub zeros otherwise.
    """

    def __init__(self, enable_multi_level: bool = False) -> None:
        self.enable_multi_level = enable_multi_level
        self._l1 = MemoryCache()
        # Expose an object with async clear() for API compatibility
        self.cache = _AsyncClearable()
        self.warmer = None  # Placeholder; can be wired to a real warmer later

    def get_stats(self) -> dict[str, Any]:
        """Return cache stats, delegating to the real SemanticCache if available."""
        real = _shared_semantic_cache
        if real is not None:
            try:
                return real.get_stats()
            except (AttributeError, TypeError, RuntimeError):
                pass
        # Fallback stub
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


# Module-level reference to the shared SemanticCache instance.
# Set by ``register_semantic_cache()`` when the pipeline creates its cache.
_shared_semantic_cache: Any = None


def register_semantic_cache(cache: Any) -> None:
    """Register the shared SemanticCache so health endpoints can read its stats."""
    global _shared_semantic_cache
    _shared_semantic_cache = cache


def get_registered_semantic_cache() -> Any:
    """Return the registered SemanticCache, or None."""
    return _shared_semantic_cache
