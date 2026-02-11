"""In-memory ephemeral storage with TTL and bounded capacity.

This store is process-local by design and intended for short-lived workflow
artifacts (for example, web-scraping ephemeral results).
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

_EPHEMERAL_STORE_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    OSError,
    TypeError,
    ValueError,
)


def _safe_int_env(var_name: str, default: int) -> int:
    raw = os.getenv(var_name)
    if raw is None:
        return default
    try:
        parsed = int(str(raw).strip())
    except _EPHEMERAL_STORE_NONCRITICAL_EXCEPTIONS:
        return default
    return parsed if parsed >= 0 else default


@dataclass(slots=True)
class _EphemeralEntry:
    payload: Any
    created_at: float
    expires_at: float
    size_bytes: int


class EphemeralStorage:
    """Process-local ephemeral key-value store with TTL and capacity caps."""

    def __init__(
        self,
        *,
        default_ttl_seconds: int = 900,
        max_entries: int = 256,
        max_bytes: int = 0,
        clock: Callable[[], float] | None = None,
    ):
        self.default_ttl_seconds = max(0, int(default_ttl_seconds))
        self.max_entries = max(1, int(max_entries)) if int(max_entries) > 0 else 1
        self.max_bytes = max(0, int(max_bytes))
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._store: OrderedDict[str, _EphemeralEntry] = OrderedDict()
        self._total_bytes = 0

    @staticmethod
    def _estimate_size_bytes(data: Any) -> int:
        """Estimate payload size in bytes for optional memory cap enforcement."""
        try:
            encoded = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            return len(encoded)
        except _EPHEMERAL_STORE_NONCRITICAL_EXCEPTIONS:
            try:
                return len(repr(data).encode("utf-8", errors="ignore"))
            except _EPHEMERAL_STORE_NONCRITICAL_EXCEPTIONS:
                return 0

    def _evict_key_locked(self, key: str) -> None:
        entry = self._store.pop(key, None)
        if entry is None:
            return
        self._total_bytes = max(0, self._total_bytes - max(0, int(entry.size_bytes)))

    def _prune_expired_locked(self, now: float) -> int:
        expired_keys = [
            key for key, entry in self._store.items()
            if entry.expires_at <= now
        ]
        for key in expired_keys:
            self._evict_key_locked(key)
        return len(expired_keys)

    def _enforce_capacity_locked(self) -> int:
        evicted = 0
        while len(self._store) > self.max_entries:
            key, _entry = self._store.popitem(last=False)
            self._total_bytes = max(0, self._total_bytes - max(0, int(_entry.size_bytes)))
            evicted += 1

        if self.max_bytes > 0:
            while self._store and self._total_bytes > self.max_bytes:
                key, _entry = self._store.popitem(last=False)
                self._total_bytes = max(0, self._total_bytes - max(0, int(_entry.size_bytes)))
                evicted += 1

        return evicted

    def store_data(self, data: Any, *, ttl_seconds: int | None = None) -> str:
        """Store a payload and return its ephemeral ID.

        The store prunes expired entries before insertion and enforces caps
        afterward with deterministic oldest-first eviction.
        """
        ttl = self.default_ttl_seconds if ttl_seconds is None else max(0, int(ttl_seconds))
        now = float(self._clock())
        expires_at = now + ttl
        entry_size = self._estimate_size_bytes(data)
        if self.max_bytes > 0 and entry_size > self.max_bytes:
            raise ValueError(
                f"Payload size {entry_size} exceeds max_bytes limit {self.max_bytes}"
            )
        ephemeral_id = str(uuid.uuid4())

        with self._lock:
            self._prune_expired_locked(now)
            self._store[ephemeral_id] = _EphemeralEntry(
                payload=data,
                created_at=now,
                expires_at=expires_at,
                size_bytes=entry_size,
            )
            self._total_bytes += max(0, int(entry_size))
            self._enforce_capacity_locked()

        return ephemeral_id

    def get_data(self, ephemeral_id: str) -> Any | None:
        """Return payload for a key, or None if missing/expired."""
        now = float(self._clock())
        with self._lock:
            self._prune_expired_locked(now)
            entry = self._store.get(ephemeral_id)
            if entry is None:
                return None
            return entry.payload

    def remove_data(self, ephemeral_id: str) -> bool:
        """Remove a payload by key. Returns True when removed."""
        with self._lock:
            if ephemeral_id not in self._store:
                return False
            self._evict_key_locked(ephemeral_id)
            return True

    def prune_expired(self) -> int:
        """Prune expired entries and return number of removed items."""
        now = float(self._clock())
        with self._lock:
            return self._prune_expired_locked(now)

    def get_stats(self) -> dict[str, int]:
        """Return current store stats for diagnostics/tests."""
        now = float(self._clock())
        with self._lock:
            self._prune_expired_locked(now)
            return {
                "entries": len(self._store),
                "total_bytes": self._total_bytes,
                "max_entries": self.max_entries,
                "max_bytes": self.max_bytes,
                "default_ttl_seconds": self.default_ttl_seconds,
            }


ephemeral_storage = EphemeralStorage(
    default_ttl_seconds=_safe_int_env("EPHEMERAL_STORE_TTL_SECONDS", 900),
    max_entries=_safe_int_env("EPHEMERAL_STORE_MAX_ENTRIES", 256),
    max_bytes=_safe_int_env("EPHEMERAL_STORE_MAX_BYTES", 0),
)
