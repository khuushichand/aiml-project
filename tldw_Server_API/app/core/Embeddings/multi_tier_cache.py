# multi_tier_cache.py
# Multi-tier caching system for embeddings with L1 (memory), L2 (disk), and L3 (remote) caches

import asyncio
import builtins
import contextlib
import functools
import hashlib
import io
import json
import os
import pickle
import tempfile
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from tldw_Server_API.app.core.Embeddings.metrics_integration import get_metrics
from tldw_Server_API.app.core.Infrastructure.redis_factory import create_sync_redis_client
from tldw_Server_API.app.core.Metrics import get_metrics_registry

_CACHE_NONCRITICAL_EXCEPTIONS = (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    AttributeError,
    ConnectionError,
    TimeoutError,
    pickle.PickleError,
    json.JSONDecodeError,
)


@dataclass
class CacheEntry:
    """Represents a cache entry"""
    key: str
    value: Any
    size_bytes: int
    created_at: float
    last_accessed: float
    access_count: int
    ttl: Optional[int] = None

    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def update_access(self):
        """Update access statistics"""
        self.last_accessed = time.time()
        self.access_count += 1


class _SafeUnpickler(pickle.Unpickler):
    """Restrictive unpickler for cache values."""

    _SAFE_BUILTINS = {
        "dict",
        "list",
        "set",
        "tuple",
        "str",
        "bytes",
        "int",
        "float",
        "bool",
    }

    def find_class(self, module, name):  # type: ignore[override]
        if module == "builtins" and name in self._SAFE_BUILTINS:
            return getattr(builtins, name)
        if module == "collections" and name == "OrderedDict":
            return OrderedDict
        raise pickle.UnpicklingError(f"Disallowed type: {module}.{name}")


def _safe_pickle_load(file_obj) -> Any:
    """Safely unpickle from a file-like object."""
    return _SafeUnpickler(file_obj).load()


def _safe_pickle_loads(data: bytes) -> Any:
    """Safely unpickle from bytes."""
    return _SafeUnpickler(io.BytesIO(data)).load()


class L1MemoryCache:
    """
    Level 1 cache - In-memory LRU cache for hot data.
    Fastest access, limited size.
    """

    def __init__(self, max_size_mb: int = 512, ttl_seconds: int = 300):
        """
        Initialize L1 memory cache.

        Args:
            max_size_mb: Maximum cache size in MB
            ttl_seconds: Default TTL for entries
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = ttl_seconds
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.current_size_bytes = 0
        self._lock = threading.RLock()
        self.metrics = get_metrics()

        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired': 0
        }

        logger.info(f"L1 Memory cache initialized: {max_size_mb}MB, TTL={ttl_seconds}s")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key not in self.cache:
                self.stats['misses'] += 1
                self.metrics.log_cache_miss("L1")
                return None

            entry = self.cache[key]

            # Check expiration
            if entry.is_expired():
                self._remove_entry(key)
                self.stats['expired'] += 1
                self.stats['misses'] += 1
                self.metrics.log_cache_miss("L1")
                return None

            # Update LRU order
            self.cache.move_to_end(key)
            entry.update_access()

            self.stats['hits'] += 1
            self.metrics.log_cache_hit("L1")

            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        if ttl is not None and ttl <= 0:
            return False
        with self._lock:
            # Calculate size
            size_bytes = self._estimate_size(value)
            if key in self.cache:
                existing_entry = self.cache[key]
                self.current_size_bytes = max(0, self.current_size_bytes - existing_entry.size_bytes)
                del self.cache[key]

            # Check if we need to evict entries
            while self.current_size_bytes + size_bytes > self.max_size_bytes:
                if not self._evict_lru():
                    return False  # Cannot make space

            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                size_bytes=size_bytes,
                created_at=time.time(),
                last_accessed=time.time(),
                access_count=0,
                ttl=self.default_ttl if ttl is None else ttl
            )

            # Add to cache
            self.cache[key] = entry
            self.current_size_bytes += size_bytes

            return True

    def _evict_lru(self) -> bool:
        """Evict least recently used entry"""
        if not self.cache:
            return False

        # Get oldest entry (first in OrderedDict)
        key = next(iter(self.cache))
        self._remove_entry(key)
        self.stats['evictions'] += 1

        return True

    def _remove_entry(self, key: str):
        """Remove an entry from cache"""
        if key in self.cache:
            entry = self.cache[key]
            self.current_size_bytes -= entry.size_bytes
            del self.cache[key]

    def _estimate_size(self, value: Any) -> int:
        """Estimate size of value in bytes"""
        try:
            return len(pickle.dumps(value))
        except _CACHE_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"Failed to estimate pickle size; using default. error={e}")
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "embeddings_cache", "event": "l1_estimate_size_failed"},
                )
            except _CACHE_NONCRITICAL_EXCEPTIONS:
                logger.debug("metrics increment failed for embeddings_cache l1_estimate_size_failed")
            return 1024  # Default estimate

    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self.cache.clear()
            self.current_size_bytes = 0

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        hit_rate = (self.stats['hits'] /
                   (self.stats['hits'] + self.stats['misses']) * 100
                   if self.stats['hits'] + self.stats['misses'] > 0 else 0)

        return {
            'level': 'L1',
            'entries': len(self.cache),
            'size_mb': self.current_size_bytes / (1024 * 1024),
            'max_size_mb': self.max_size_bytes / (1024 * 1024),
            'hit_rate': f"{hit_rate:.1f}%",
            **self.stats
        }


class L2DiskCache:
    """
    Level 2 cache - Disk-based cache for warm data.
    Slower than memory but larger capacity.
    """

    def __init__(self, cache_dir: str = "./cache/l2", max_size_gb: int = 10, ttl_seconds: int = 3600):
        """
        Initialize L2 disk cache.

        Args:
            cache_dir: Directory for cache files
            max_size_gb: Maximum cache size in GB
            ttl_seconds: Default TTL for entries
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_size_bytes = max_size_gb * 1024 * 1024 * 1024
        self.default_ttl = ttl_seconds
        self.index: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.metrics = get_metrics()

        # Load existing index
        self._load_index()

        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired': 0
        }

        logger.info(f"L2 Disk cache initialized: {cache_dir}, {max_size_gb}GB")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key not in self.index:
                self.stats['misses'] += 1
                self.metrics.log_cache_miss("L2")
                return None

            entry_info = self.index[key]

            # Check expiration
            if self._is_expired(entry_info):
                self._remove_entry(key)
                self.stats['expired'] += 1
                self.stats['misses'] += 1
                self.metrics.log_cache_miss("L2")
                return None

            # Read from disk
            file_path = self.cache_dir / entry_info['file']

            try:
                with open(file_path, 'rb') as f:
                    value = _safe_pickle_load(f)

                # Update access time
                entry_info['last_accessed'] = time.time()
                entry_info['access_count'] += 1

                self.stats['hits'] += 1
                self.metrics.log_cache_hit("L2")

                return value

            except _CACHE_NONCRITICAL_EXCEPTIONS as e:
                logger.error(f"Error reading L2 cache file {file_path}: {e}")
                try:
                    get_metrics_registry().increment(
                        "app_exception_events_total",
                        labels={"component": "embeddings_cache", "event": "l2_read_error"},
                    )
                except _CACHE_NONCRITICAL_EXCEPTIONS:
                    logger.debug("metrics increment failed for embeddings_cache l2_read_error")
                self._remove_entry(key)
                self.stats['misses'] += 1
                return None

    def get_access_count(self, key: str) -> int:
        """Return the current access count for a cached item."""
        with self._lock:
            entry_info = self.index.get(key)
            if not entry_info:
                return 0
            return int(entry_info.get('access_count', 0))

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        if ttl is not None and ttl <= 0:
            return False
        with self._lock:
            # Generate file name
            file_name = f"{hashlib.md5(key.encode()).hexdigest()}.cache"
            file_path = self.cache_dir / file_name

            try:
                tmp_path = None

                # Write to a temp file first so we don't corrupt an existing entry on failure
                with tempfile.NamedTemporaryFile(dir=self.cache_dir, delete=False, suffix=".tmp") as tmp_file:
                    pickle.dump(value, tmp_file)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())
                    tmp_path = Path(tmp_file.name)

                # Get file size
                size_bytes = tmp_path.stat().st_size if tmp_path else 0

                def _total_excluding_current() -> int:
                    total_size = self._get_total_size()
                    if key in self.index:
                        with contextlib.suppress(_CACHE_NONCRITICAL_EXCEPTIONS):
                            total_size -= int(self.index[key].get('size_bytes') or 0)
                    return max(0, total_size)

                # Check total cache size and evict until we have room
                total = _total_excluding_current()
                if total + size_bytes > self.max_size_bytes:
                    # Keep evicting while over capacity and there are entries to evict
                    while total + size_bytes > self.max_size_bytes and self.index:
                        self._evict_lru()
                        total = _total_excluding_current()
                    if total + size_bytes > self.max_size_bytes:
                        # Give up: refuse to cache this entry and clean up temp file
                        try:
                            if tmp_path and tmp_path.exists():
                                tmp_path.unlink()
                        except _CACHE_NONCRITICAL_EXCEPTIONS as de:
                            logger.debug(f"L2 cleanup temp unlink failed at capacity: {de}")
                            try:
                                get_metrics_registry().increment(
                                    "app_warning_events_total",
                                    labels={"component": "embeddings_cache", "event": "l2_unlink_failed"},
                                )
                            except _CACHE_NONCRITICAL_EXCEPTIONS:
                                logger.debug("metrics increment failed for embeddings_cache l2_unlink_failed")
                        # Ensure index doesn't reference missing files after a failed update
                        try:
                            if key in self.index:
                                existing_file = self.cache_dir / self.index[key].get('file', '')
                                if not existing_file.exists():
                                    self.index.pop(key, None)
                                    self._save_index()
                        except _CACHE_NONCRITICAL_EXCEPTIONS:
                            pass
                        logger.warning(f"L2 Disk cache at capacity; refusing to cache key {key}")
                        return False

                # Replace the existing cache file atomically
                if tmp_path:
                    os.replace(tmp_path, file_path)
                    tmp_path = None

                # Update index
                self.index[key] = {
                    'file': file_name,
                    'size_bytes': size_bytes,
                    'created_at': time.time(),
                    'last_accessed': time.time(),
                    'access_count': 0,
                    'ttl': self.default_ttl if ttl is None else ttl
                }

                # Save index
                self._save_index()

                return True

            except _CACHE_NONCRITICAL_EXCEPTIONS as e:
                try:
                    if 'tmp_path' in locals() and tmp_path and tmp_path.exists():
                        tmp_path.unlink()
                except _CACHE_NONCRITICAL_EXCEPTIONS:
                    pass
                logger.error(f"Error writing L2 cache file {file_path}: {e}")
                try:
                    get_metrics_registry().increment(
                        "app_exception_events_total",
                        labels={"component": "embeddings_cache", "event": "l2_write_error"},
                    )
                except _CACHE_NONCRITICAL_EXCEPTIONS:
                    logger.debug("metrics increment failed for embeddings_cache l2_write_error")
                return False

    def _is_expired(self, entry_info: dict[str, Any]) -> bool:
        """Check if entry has expired"""
        if entry_info.get('ttl') is None:
            return False
        return time.time() - entry_info['created_at'] > entry_info['ttl']

    def _evict_lru(self):
        """Evict least recently used entries"""
        # Sort by last access time
        sorted_entries = sorted(
            self.index.items(),
            key=lambda x: x[1]['last_accessed']
        )

        # Remove oldest 10% of entries
        num_to_remove = max(1, len(sorted_entries) // 10)

        for key, _ in sorted_entries[:num_to_remove]:
            self._remove_entry(key, persist=False)
            self.stats['evictions'] += 1
        self._save_index()

    def _remove_entry(self, key: str, persist: bool = True):
        """Remove an entry from cache"""
        if key in self.index:
            entry_info = self.index[key]
            file_path = self.cache_dir / entry_info['file']

            try:
                file_path.unlink()
            except _CACHE_NONCRITICAL_EXCEPTIONS as e:
                logger.debug(f"Failed to remove L2 cache file during eviction: file={file_path}, error={e}")
                try:
                    get_metrics_registry().increment(
                        "app_warning_events_total",
                        labels={"component": "embeddings_cache", "event": "l2_evict_delete_failed"},
                    )
                except _CACHE_NONCRITICAL_EXCEPTIONS:
                    logger.debug("metrics increment failed for embeddings_cache l2_evict_delete_failed")

            del self.index[key]
            if persist:
                self._save_index()

    def _get_total_size(self) -> int:
        """Get total size of cached files"""
        return sum(entry['size_bytes'] for entry in self.index.values())

    def _load_index(self):
        """Load index from disk"""
        index_file = self.cache_dir / "index.json"

        if index_file.exists():
            try:
                with open(index_file) as f:
                    self.index = json.load(f)
                logger.info(f"Loaded L2 cache index with {len(self.index)} entries")
            except _CACHE_NONCRITICAL_EXCEPTIONS as e:
                logger.error(f"Error loading L2 cache index: {e}")
                self.index = {}

    def _save_index(self):
        """Save index to disk"""
        index_file = self.cache_dir / "index.json"
        tmp_file = index_file.with_suffix(".json.tmp")

        try:
            with open(tmp_file, 'w') as f:
                json.dump(self.index, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, index_file)
        except _CACHE_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Error saving L2 cache index: {e}")
            try:
                if tmp_file.exists():
                    tmp_file.unlink()
            except _CACHE_NONCRITICAL_EXCEPTIONS:
                pass

    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            # Remove all cache files
            for entry in self.index.values():
                file_path = self.cache_dir / entry['file']
                try:
                    file_path.unlink()
                except _CACHE_NONCRITICAL_EXCEPTIONS as e:
                    logger.debug(f"Failed to remove L2 cache file during clear: file={file_path}, error={e}")

            self.index.clear()
            self._save_index()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        hit_rate = (self.stats['hits'] /
                   (self.stats['hits'] + self.stats['misses']) * 100
                   if self.stats['hits'] + self.stats['misses'] > 0 else 0)

        return {
            'level': 'L2',
            'entries': len(self.index),
            'size_gb': self._get_total_size() / (1024 * 1024 * 1024),
            'max_size_gb': self.max_size_bytes / (1024 * 1024 * 1024),
            'hit_rate': f"{hit_rate:.1f}%",
            **self.stats
        }


class L3RemoteCache:
    """
    Level 3 cache - Remote cache (Redis) for distributed caching.
    Shared across instances.
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        ttl_seconds: int = 7200,
        key_prefix: str = "emb:"
    ):
        """
        Initialize L3 remote cache.

        Args:
            redis_host: Redis host
            redis_port: Redis port
            redis_db: Redis database number
            ttl_seconds: Default TTL for entries
            key_prefix: Prefix for cache keys
        """
        self.redis_client = None
        self.default_ttl = ttl_seconds
        self.key_prefix = key_prefix
        self.metrics = get_metrics()

        # Try to connect to Redis
        try:
            preferred_url = f"redis://{redis_host}:{int(redis_port)}/{int(redis_db)}"
            self.redis_client = create_sync_redis_client(
                preferred_url=preferred_url,
                context="embeddings_l3_cache",
                fallback_to_fake=True,
                decode_responses=False,
            )
            self.enabled = True
            if getattr(self.redis_client, "_tldw_is_stub", False):
                logger.info("L3 Remote cache using in-memory stub (Redis unavailable)")
            else:
                logger.info(f"L3 Remote cache connected to Redis at {redis_host}:{redis_port}")
        except _CACHE_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"L3 Remote cache disabled, Redis not available: {e}")
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "embeddings_cache", "event": "l3_redis_unavailable"},
                )
            except _CACHE_NONCRITICAL_EXCEPTIONS:
                logger.debug("metrics increment failed for embeddings_cache l3_redis_unavailable")
            self.enabled = False

        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0
        }

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled:
            return None

        full_key = f"{self.key_prefix}{key}"

        try:
            data = self.redis_client.get(full_key)

            if data is None:
                self.stats['misses'] += 1
                self.metrics.log_cache_miss("L3")
                return None

            value = _safe_pickle_loads(data)
            self.stats['hits'] += 1
            self.metrics.log_cache_hit("L3")

            return value

        except _CACHE_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Error reading from L3 cache: {e}")
            try:
                get_metrics_registry().increment(
                    "app_exception_events_total",
                    labels={"component": "embeddings_cache", "event": "l3_read_error"},
                )
            except _CACHE_NONCRITICAL_EXCEPTIONS:
                logger.debug("metrics increment failed for embeddings_cache l3_read_error")
            self.stats['errors'] += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        if not self.enabled:
            return False
        if ttl is not None and ttl <= 0:
            return False

        full_key = f"{self.key_prefix}{key}"

        try:
            data = pickle.dumps(value)
            self.redis_client.setex(
                full_key,
                self.default_ttl if ttl is None else ttl,
                data
            )
            return True

        except _CACHE_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Error writing to L3 cache: {e}")
            try:
                get_metrics_registry().increment(
                    "app_exception_events_total",
                    labels={"component": "embeddings_cache", "event": "l3_write_error"},
                )
            except _CACHE_NONCRITICAL_EXCEPTIONS:
                logger.debug("metrics increment failed for embeddings_cache l3_write_error")
            self.stats['errors'] += 1
            return False

    def clear(self):
        """Clear all cache entries with our prefix"""
        if not self.enabled:
            return

        try:
            # Find all keys with our prefix
            pattern = f"{self.key_prefix}*"
            keys = self.redis_client.keys(pattern)

            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} entries from L3 cache")

        except _CACHE_NONCRITICAL_EXCEPTIONS as e:
            logger.error(f"Error clearing L3 cache: {e}")
            try:
                get_metrics_registry().increment(
                    "app_exception_events_total",
                    labels={"component": "embeddings_cache", "event": "l3_clear_error"},
                )
            except _CACHE_NONCRITICAL_EXCEPTIONS:
                logger.debug("metrics increment failed for embeddings_cache l3_clear_error")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        hit_rate = (self.stats['hits'] /
                   (self.stats['hits'] + self.stats['misses']) * 100
                   if self.stats['hits'] + self.stats['misses'] > 0 else 0)

        stats = {
            'level': 'L3',
            'enabled': self.enabled,
            'hit_rate': f"{hit_rate:.1f}%",
            **self.stats
        }

        # Add Redis info if available
        if self.enabled:
            try:
                info = self.redis_client.info('memory')
                stats['memory_used_mb'] = info.get('used_memory', 0) / (1024 * 1024)
            except _CACHE_NONCRITICAL_EXCEPTIONS as e:
                logger.debug(f"Failed to fetch Redis memory info: error={e}")
                try:
                    get_metrics_registry().increment(
                        "app_warning_events_total",
                        labels={"component": "embeddings_cache", "event": "l3_info_failed"},
                    )
                except _CACHE_NONCRITICAL_EXCEPTIONS:
                    logger.debug("metrics increment failed for embeddings_cache l3_info_failed")

        return stats


class MultiTierCache:
    """
    Multi-tier cache orchestrator.
    Manages L1, L2, and L3 caches with automatic promotion/demotion.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Initialize multi-tier cache.

        Args:
            config: Configuration dictionary
        """
        config = config or {}

        # Initialize cache tiers
        self.l1 = L1MemoryCache(
            max_size_mb=config.get('l1_size_mb', 512),
            ttl_seconds=config.get('l1_ttl', 300)
        )

        self.l2 = L2DiskCache(
            cache_dir=config.get('l2_dir', './cache/l2'),
            max_size_gb=config.get('l2_size_gb', 10),
            ttl_seconds=config.get('l2_ttl', 3600)
        )

        self.l3 = L3RemoteCache(
            redis_host=config.get('redis_host', 'localhost'),
            redis_port=config.get('redis_port', 6379),
            ttl_seconds=config.get('l3_ttl', 7200)
        )

        # Promotion thresholds
        self.l2_to_l1_threshold = config.get('l2_to_l1_threshold', 5)  # Access count
        self.l3_to_l2_threshold = config.get('l3_to_l2_threshold', 3)

        logger.info("Multi-tier cache initialized with L1, L2, and L3 tiers")
        self._sync_loop_warned = False

    async def _call_in_executor(self, func: Callable[..., Any], *args, **kwargs):
        """Run a blocking cache operation in the default executor."""
        loop = asyncio.get_running_loop()
        bound = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, bound)

    async def get_async(self, key: str) -> Optional[Any]:
        """Async get from cache with automatic promotion"""
        # Try L1
        value = self.l1.get(key)
        if value is not None:
            return value

        # Try L2
        value = await self._call_in_executor(self.l2.get, key)
        if value is not None:
            access_count = self.l2.get_access_count(key)
            if access_count >= self.l2_to_l1_threshold:
                self.l1.set(key, value)
            return value

        # Try L3
        if self.l3.enabled:
            value = await self._call_in_executor(self.l3.get, key)
            if value is not None:
                await self._call_in_executor(self.l2.set, key, value, None)
                self.l1.set(key, value)
                return value

        return None

    def _get_sync(self, key: str) -> Optional[Any]:
        """Synchronous get for use inside a running loop (L1 only to avoid blocking)."""
        value = self.l1.get(key)
        if value is not None:
            return value
        return None

    def get(self, key: str) -> Optional[Any]:
        """Synchronous get from cache"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            if not self._sync_loop_warned:
                self._sync_loop_warned = True
                logger.warning(
                    "MultiTierCache.get called from a running event loop; "
                    "returning L1-only. Use await get_async for L2/L3."
                )
            return self._get_sync(key)

        return asyncio.run(self.get_async(key))

    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Async set in cache"""
        if ttl is not None and ttl <= 0:
            return False
        # Always write to L1 for immediate access
        success = self.l1.set(key, value, ttl)

        # Write-through to L2 and L3 using executor offloads
        if success:
            await self._call_in_executor(self.l2.set, key, value, ttl)

            if self.l3.enabled:
                await self._call_in_executor(self.l3.set, key, value, ttl)

        return success

    def _set_sync(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Synchronous set for use inside a running loop (L1 only to avoid blocking)."""
        if ttl is not None and ttl <= 0:
            return False
        return self.l1.set(key, value, ttl)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Synchronous set in cache"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            if not self._sync_loop_warned:
                self._sync_loop_warned = True
                logger.warning(
                    "MultiTierCache.set called from a running event loop; "
                    "writing L1-only. Use await set_async for L2/L3."
                )
            return self._set_sync(key, value, ttl)

        return asyncio.run(self.set_async(key, value, ttl))

    def invalidate(self, key: str):
        """Invalidate entry across all tiers"""
        # Remove from L1
        with self.l1._lock:
            if key in self.l1.cache:
                self.l1._remove_entry(key)

        # Remove from L2
        with self.l2._lock:
            if key in self.l2.index:
                self.l2._remove_entry(key)

        # Remove from L3
        if self.l3.enabled:
            full_key = f"{self.l3.key_prefix}{key}"
            try:
                self.l3.redis_client.delete(full_key)
            except _CACHE_NONCRITICAL_EXCEPTIONS as e:
                logger.debug(f"Failed to delete L3 cache key: key={full_key}, error={e}")
                try:
                    get_metrics_registry().increment(
                        "app_warning_events_total",
                        labels={"component": "embeddings_cache", "event": "l3_delete_failed"},
                    )
                except _CACHE_NONCRITICAL_EXCEPTIONS:
                    logger.debug("metrics increment failed for embeddings_cache l3_delete_failed")

    def clear_all(self):
        """Clear all cache tiers"""
        self.l1.clear()
        self.l2.clear()
        self.l3.clear()
    def get_statistics(self) -> dict[str, Any]:
        """Get statistics for all tiers"""
        return {
            'l1': self.l1.get_stats(),
            'l2': self.l2.get_stats(),
            'l3': self.l3.get_stats(),
            'total_entries': (
                len(self.l1.cache) +
                len(self.l2.index) +
                (self.l3.redis_client.dbsize() if self.l3.enabled else 0)
            )
        }


# Global multi-tier cache
_multi_tier_cache: Optional[MultiTierCache] = None


def get_multi_tier_cache() -> MultiTierCache:
    """Get or create the global multi-tier cache."""
    global _multi_tier_cache
    if _multi_tier_cache is None:
        _multi_tier_cache = MultiTierCache()
    return _multi_tier_cache


# Cache decorator for automatic caching
def cached(ttl: int = 300, cache_tier: str = "multi"):
    """
    Decorator for automatic caching of function results.

    Args:
        ttl: Time to live in seconds
        cache_tier: Which tier to use (l1, l2, l3, multi)
    """
    def decorator(func):
        cache = get_multi_tier_cache()

        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                # Create cache key from function name and arguments
                key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

                # Try to get from cache
                if cache_tier == "multi":
                    value = await cache.get_async(key)
                else:
                    tier = getattr(cache, cache_tier.lower(), cache.l1)
                    value = tier.get(key)

                if value is not None:
                    return value

                # Compute value
                value = await func(*args, **kwargs)

                # Store in cache
                if cache_tier == "multi":
                    await cache.set_async(key, value, ttl)
                else:
                    tier = getattr(cache, cache_tier.lower(), cache.l1)
                    tier.set(key, value, ttl)

                return value
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                # Create cache key
                key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

                # Try to get from cache
                if cache_tier == "multi":
                    value = cache.get(key)
                else:
                    tier = getattr(cache, cache_tier.lower(), cache.l1)
                    value = tier.get(key)

                if value is not None:
                    return value

                # Compute value
                value = func(*args, **kwargs)

                # Store in cache
                if cache_tier == "multi":
                    cache.set(key, value, ttl)
                else:
                    tier = getattr(cache, cache_tier.lower(), cache.l1)
                    tier.set(key, value, ttl)

                return value
            return sync_wrapper
    return decorator
