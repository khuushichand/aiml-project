from __future__ import annotations

import asyncio
import inspect
import os
import time
import threading
import hashlib
import fnmatch
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.config import settings

try:  # pragma: no cover - import guard
    import redis  # type: ignore
    import redis.asyncio as aioredis  # type: ignore
except Exception as exc:  # pragma: no cover
    redis = None  # type: ignore
    aioredis = None  # type: ignore
    _import_error = exc
else:
    _import_error = None

_ASYNC_STUB_CACHE: Dict[str, "InMemoryAsyncRedis"] = {}

try:  # pragma: no cover - optional metrics dependency
    from tldw_Server_API.app.core.Metrics.metrics_manager import (
        get_metrics_registry as _get_metrics_registry,
    )
except Exception:  # pragma: no cover - metrics optional during early startup
    _get_metrics_registry = None  # type: ignore[assignment]

DEFAULT_REDIS_URL = "redis://localhost:6379"


def _settings_lookup(*keys: str) -> Optional[str]:
    for key in keys:
        try:
            value = settings.get(key)  # type: ignore[attr-defined]
            if isinstance(value, str) and value.strip():
                return value
        except Exception:
            pass
        env = os.getenv(key)
        if env is not None and env.strip():
            return env
    return None


def _resolve_url(preferred: Optional[str] = None) -> str:
    if preferred and str(preferred).strip():
        return str(preferred).strip()
    url = _settings_lookup("EMBEDDINGS_REDIS_URL", "REDIS_URL")
    return url or DEFAULT_REDIS_URL


def _metrics_registry():
    if _get_metrics_registry is None:
        return None
    try:
        return _get_metrics_registry()
    except Exception:
        return None


def _record_connection_metrics(
    *,
    mode: str,
    context: str,
    outcome: str,
    start_time: float,
    error: Optional[BaseException] = None,
):
    registry = _metrics_registry()
    if registry is None:
        return

    elapsed = max(time.perf_counter() - start_time, 0.0)
    labels = {"mode": mode, "context": context, "outcome": outcome}
    try:
        registry.increment("infra_redis_connection_attempts_total", 1, labels)
        registry.observe("infra_redis_connection_duration_seconds", elapsed, labels)
        if outcome == "stub":
            reason = type(error).__name__ if error else "fallback"
            registry.increment(
                "infra_redis_fallback_total",
                1,
                {"mode": mode, "context": context, "reason": reason},
            )
        elif outcome == "error":
            reason = type(error).__name__ if error else "unknown"
            registry.increment(
                "infra_redis_connection_errors_total",
                1,
                {"mode": mode, "context": context, "error": reason},
            )
    except Exception as metric_exc:
        logger.debug(
            "Failed to record Redis infrastructure metrics: {err}",
            err=metric_exc,
        )


async def create_async_redis_client(
    *,
    preferred_url: Optional[str] = None,
    decode_responses: bool = True,
    fallback_to_fake: bool = True,
    context: str = "default",
    redis_kwargs: Optional[dict] = None,
):
    """
    Instantiate an asyncio Redis client. Falls back to an in-memory stub when allowed.

    Args:
        preferred_url: Explicit URL to prioritize (e.g., embeddings queue).
        decode_responses: Whether to decode bytes into str.
        fallback_to_fake: If True, transparently fallback to an in-memory stub when
            the real server is unreachable.
        context: Human-readable label for logging (helps trace callers).

    Returns:
        An asyncio Redis client implementing the standard redis-py API.
    """

    if aioredis is None:
        raise RuntimeError(
            "redis[asyncio] is required but not installed"
        ) from _import_error

    url = _resolve_url(preferred_url)
    context_label = (context or "default").strip() or "default"
    options = dict(redis_kwargs or {})
    if "decode_responses" not in options:
        options["decode_responses"] = decode_responses
    start_time = time.perf_counter()

    client = None
    decode_option = options.get("decode_responses", decode_responses)
    try:
        candidate = aioredis.from_url(url, **options)
        if inspect.isawaitable(candidate):  # redis<5 compatibility
            candidate = await candidate
        client = candidate
        ping = getattr(client, "ping", None)
        if ping is None:
            _record_connection_metrics(
                mode="async",
                context=context_label,
                outcome="stub",
                start_time=start_time,
            )
            return client
        result = ping()
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass
        if not fallback_to_fake:
            _record_connection_metrics(
                mode="async",
                context=context_label,
                outcome="error",
                start_time=start_time,
                error=exc,
            )
            raise
        logger.warning(
            "Redis unavailable at {url} for {context}; using in-memory stub. Error: {err}",
            url=url,
            context=context_label,
            err=exc,
        )
        cache_key = f"{url}::{context_label}::{decode_option}"
        fake_client = _ASYNC_STUB_CACHE.get(cache_key)
        if fake_client is None:
            fake_client = InMemoryAsyncRedis(decode_responses=decode_option)
            _ASYNC_STUB_CACHE[cache_key] = fake_client
        setattr(fake_client, "_tldw_is_stub", True)
        await fake_client.ping()
        _record_connection_metrics(
            mode="async",
            context=context_label,
            outcome="stub",
            start_time=start_time,
            error=exc,
        )
        return fake_client

    _record_connection_metrics(
        mode="async",
        context=context_label,
        outcome="real",
        start_time=start_time,
    )
    return client


def create_sync_redis_client(
    *,
    preferred_url: Optional[str] = None,
    decode_responses: bool = True,
    fallback_to_fake: bool = True,
    context: str = "default",
    redis_kwargs: Optional[dict] = None,
):
    """
    Instantiate a synchronous Redis client with optional in-memory fallback.
    """

    if redis is None:
        raise RuntimeError(
            "redis client is required but not installed"
        ) from _import_error

    url = _resolve_url(preferred_url)
    context_label = (context or "default").strip() or "default"
    options = dict(redis_kwargs or {})
    if "decode_responses" not in options:
        options["decode_responses"] = decode_responses
    start_time = time.perf_counter()
    client = None

    try:
        client = redis.from_url(url, **options)
        client.ping()
    except Exception as exc:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        if not fallback_to_fake:
            _record_connection_metrics(
                mode="sync",
                context=context_label,
                outcome="error",
                start_time=start_time,
                error=exc,
            )
            raise
        logger.warning(
            "Redis unavailable at {url} for {context}; using in-memory stub. Error: {err}",
            url=url,
            context=context_label,
            err=exc,
        )
        fake_client = InMemorySyncRedis(
            decode_responses=options.get("decode_responses", True)
        )
        fake_client.ping()
        _record_connection_metrics(
            mode="sync",
            context=context_label,
            outcome="stub",
            start_time=start_time,
            error=exc,
        )
        return fake_client

    _record_connection_metrics(
        mode="sync",
        context=context_label,
        outcome="real",
        start_time=start_time,
    )
    return client


class _InMemoryRedisCore:
    """Stateful in-memory substitute implementing minimal Redis behaviors."""

    def __init__(self, decode_responses: bool = True):
        self.decode_responses = decode_responses
        self._strings: Dict[str, str] = {}
        self._sets: Dict[str, set] = {}
        self._sorted_sets: Dict[str, Dict[str, float]] = {}
        self._hashes: Dict[str, Dict[str, str]] = {}
        self._streams: Dict[str, List[Tuple[str, Dict[str, str]]]] = {}
        self._stream_counters: Dict[str, int] = {}
        self._groups: Dict[str, set] = {}
        self._expiry: Dict[str, float] = {}
        self._scripts: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Basic utilities
    # ------------------------------------------------------------------
    def ping(self) -> bool:
        return True

    def close(self) -> None:
        pass

    def _now(self) -> float:
        return time.time()

    def _delete_internal(self, key: str) -> None:
        self._strings.pop(key, None)
        self._sets.pop(key, None)
        self._sorted_sets.pop(key, None)
        self._hashes.pop(key, None)
        self._streams.pop(key, None)
        self._stream_counters.pop(key, None)
        self._groups.pop(key, None)
        self._expiry.pop(key, None)

    def _check_expiry(self, key: str) -> None:
        expires_at = self._expiry.get(key)
        if expires_at is not None and expires_at <= self._now():
            self._delete_internal(key)

    # ------------------------------------------------------------------
    # Stream operations
    # ------------------------------------------------------------------
    def xlen(self, name: str) -> int:
        return len(self._streams.get(name, []))

    def xadd(self, name: str, fields: Dict[str, Any]) -> str:
        stream = self._streams.setdefault(name, [])
        counter = self._stream_counters.get(name, 0) + 1
        self._stream_counters[name] = counter
        entry_id = f"{int(self._now() * 1000)}-{counter}"
        stream.append((entry_id, {str(k): str(v) for k, v in fields.items()}))
        return entry_id

    def xrange(
        self,
        name: str,
        min: str = "-",  # noqa: A002 - match redis signature
        max: str = "+",
        count: Optional[int] = None,
        **kwargs: Any,
    ) -> List[Tuple[str, Dict[str, str]]]:
        minimum = kwargs.get("minimum", min)
        maximum = kwargs.get("maximum", max)
        stream = list(self._streams.get(name, []))
        if minimum not in ("-", None) or maximum not in ("+", None):
            def _within(entry_id: str) -> bool:
                ts = entry_id.split("-", 1)[0]
                if minimum not in ("-", None) and ts < str(minimum):
                    return False
                if maximum not in ("+", None) and ts > str(maximum):
                    return False
                return True
            stream = [item for item in stream if _within(item[0])]
        if count is not None and count >= 0:
            stream = stream[:count]
        return [(entry_id, dict(data)) for entry_id, data in stream]

    def xrevrange(
        self,
        name: str,
        max: str = "+",
        min: str = "-",
        count: Optional[int] = None,
        **kwargs: Any,
    ) -> List[Tuple[str, Dict[str, str]]]:
        maximum = kwargs.get("maximum", max)
        minimum = kwargs.get("minimum", min)
        stream = list(self._streams.get(name, []))
        stream.reverse()
        if minimum not in ("-", None) or maximum not in ("+", None):
            def _within(entry_id: str) -> bool:
                ts = entry_id.split("-", 1)[0]
                if maximum not in ("+", None) and ts > str(maximum):
                    return False
                if minimum not in ("-", None) and ts < str(minimum):
                    return False
                return True
            stream = [item for item in stream if _within(item[0])]
        if count is not None and count >= 0:
            stream = stream[:count]
        return [(entry_id, dict(data)) for entry_id, data in stream]

    def xdel(self, name: str, entry_id: str) -> int:
        stream = self._streams.get(name, [])
        before = len(stream)
        stream[:] = [item for item in stream if item[0] != entry_id]
        return before - len(stream)

    def xgroup_create(self, name: str, group: str, id: str = "0") -> None:
        self._groups.setdefault(name, set()).add(group)

    # ------------------------------------------------------------------
    # Set / sorted set operations
    # ------------------------------------------------------------------
    def sadd(self, key: str, member: str) -> int:
        st = self._sets.setdefault(key, set())
        before = len(st)
        st.add(str(member))
        return 1 if len(st) > before else 0

    def srem(self, key: str, member: str) -> int:
        st = self._sets.get(key)
        if st is None:
            return 0
        try:
            st.remove(str(member))
            return 1
        except KeyError:
            return 0

    def smembers(self, key: str) -> set:
        return set(self._sets.get(key, set()))

    def zadd(self, key: str, mapping: Dict[str, float]) -> None:
        zset = self._sorted_sets.setdefault(key, {})
        for member, score in mapping.items():
            zset[str(member)] = float(score)

    def zremrangebyscore(self, key: str, minimum: float, maximum: float) -> int:
        zset = self._sorted_sets.get(key)
        if not zset:
            return 0
        removed = 0
        for member in list(zset.keys()):
            score = zset[member]
            if minimum <= score <= maximum:
                del zset[member]
                removed += 1
        if not zset:
            self._sorted_sets.pop(key, None)
        return removed

    def zcard(self, key: str) -> int:
        return len(self._sorted_sets.get(key, {}))

    # ------------------------------------------------------------------
    # Hash operations
    # ------------------------------------------------------------------
    def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        target = self._hashes.setdefault(key, {})
        created = 0
        for field, value in mapping.items():
            field = str(field)
            if field not in target:
                created += 1
            target[field] = str(value)
        return created

    def hgetall(self, key: str) -> Dict[str, str]:
        return dict(self._hashes.get(key, {}))

    # ------------------------------------------------------------------
    # String operations
    # ------------------------------------------------------------------
    def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        self._strings[key] = str(value)
        if ex is not None:
            self._expiry[key] = self._now() + int(ex)

    def get(self, key: str) -> Optional[str]:
        self._check_expiry(key)
        return self._strings.get(key)

    def delete(self, key: str) -> int:
        existed = int(
            key in self._strings
            or key in self._sets
            or key in self._sorted_sets
            or key in self._hashes
            or key in self._streams
        )
        self._delete_internal(key)
        return existed

    def expire(self, key: str, seconds: int) -> None:
        if key in self._strings or key in self._sets or key in self._sorted_sets or key in self._hashes:
            self._expiry[key] = self._now() + int(seconds)

    def ttl(self, key: str) -> int:
        self._check_expiry(key)
        expires_at = self._expiry.get(key)
        if expires_at is None:
            return -1
        remaining = int(round(expires_at - self._now()))
        return remaining if remaining >= 0 else -2

    def incr(self, key: str) -> int:
        return self.incrby(key, 1)

    def incrby(self, key: str, amount: int) -> int:
        self._check_expiry(key)
        current = int(self._strings.get(key, "0"))
        current += int(amount)
        self._strings[key] = str(current)
        return current

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def scan(self, cursor: int, match: Optional[str], count: Optional[int]) -> Tuple[int, List[str]]:
        keys = set(self._strings.keys()) | set(self._sets.keys()) | set(self._sorted_sets.keys()) | set(self._hashes.keys()) | set(self._streams.keys())
        if match:
            pattern = match
            keys = {k for k in keys if fnmatch.fnmatch(k, pattern)}
        result = sorted(keys)
        if count is not None and count >= 0:
            result = result[:count]
        return 0, result

    def script_load(self, script: str) -> str:
        sha = hashlib.sha1(script.encode("utf-8")).hexdigest()
        self._scripts[sha] = script
        return sha

    def evalsha(self, sha: str, num_keys: int, *args) -> List[Any]:
        script = self._scripts.get(sha)
        if script is None:
            raise RuntimeError("NOSCRIPT")
        # Heuristic: handle the rate limiter script used by DistributedRateLimiter
        if "ZRANGE" in script and "ZREMRANGEBYSCORE" in script:
            if num_keys < 1 or len(args) < 3:
                raise RuntimeError("Invalid arguments for rate limiter script")
            redis_key = args[0]
            limit = int(args[1])
            window = int(args[2])
            current_time = float(args[3]) if len(args) > 3 else self._now()
            return self._eval_rate_limiter(redis_key, limit, window, current_time)
        raise RuntimeError("Unsupported script")

    def _eval_rate_limiter(self, redis_key: str, limit: int, window: int, current_time: float) -> List[Any]:
        zset = self._sorted_sets.setdefault(redis_key, {})
        cutoff = current_time - window
        for member in list(zset.keys()):
            if zset[member] <= cutoff:
                del zset[member]
        if len(zset) < limit:
            member_id = f"{current_time}:{len(zset)+1}"
            zset[member_id] = current_time
            return [1, 0]
        oldest = min(zset.values()) if zset else current_time
        retry_after = int(max(0, oldest + window - current_time)) or window
        return [0, retry_after]


class InMemoryAsyncRedis:
    """Asyncio-friendly wrapper around the in-memory Redis core."""

    def __init__(self, decode_responses: bool = True):
        self._core = _InMemoryRedisCore(decode_responses=decode_responses)
        self._lock = asyncio.Lock()

    async def ping(self):
        return self._core.ping()

    async def close(self):
        self._core.close()

    async def xlen(self, name: str) -> int:
        async with self._lock:
            return self._core.xlen(name)

    async def xadd(self, name: str, fields: Dict[str, Any]):
        async with self._lock:
            return self._core.xadd(name, fields)

    async def xrange(self, name: str, *args, **kwargs):
        async with self._lock:
            return self._core.xrange(name, *args, **kwargs)

    async def xrevrange(self, name: str, *args, **kwargs):
        async with self._lock:
            return self._core.xrevrange(name, *args, **kwargs)

    async def xdel(self, name: str, entry_id: str) -> int:
        async with self._lock:
            return self._core.xdel(name, entry_id)

    async def xgroup_create(self, name: str, group: str, id: str = "0") -> None:
        async with self._lock:
            self._core.xgroup_create(name, group, id)

    async def sadd(self, key: str, member: str) -> int:
        async with self._lock:
            return self._core.sadd(key, member)

    async def srem(self, key: str, member: str) -> int:
        async with self._lock:
            return self._core.srem(key, member)

    async def smembers(self, key: str):
        async with self._lock:
            return self._core.smembers(key)

    async def zadd(self, key: str, mapping: Dict[str, float]) -> None:
        async with self._lock:
            self._core.zadd(key, mapping)

    async def zremrangebyscore(self, key: str, minimum: float, maximum: float) -> int:
        async with self._lock:
            return self._core.zremrangebyscore(key, float(minimum), float(maximum))

    async def zcard(self, key: str) -> int:
        async with self._lock:
            return self._core.zcard(key)

    async def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        async with self._lock:
            return self._core.hset(key, mapping)

    async def hgetall(self, key: str) -> Dict[str, str]:
        async with self._lock:
            return self._core.hgetall(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        async with self._lock:
            self._core.set(key, value, ex=ex)

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            return self._core.get(key)

    async def delete(self, key: str) -> int:
        async with self._lock:
            return self._core.delete(key)

    async def expire(self, key: str, seconds: int) -> None:
        async with self._lock:
            self._core.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        async with self._lock:
            return self._core.ttl(key)

    async def incr(self, key: str) -> int:
        async with self._lock:
            return self._core.incr(key)

    async def incrby(self, key: str, amount: int) -> int:
        async with self._lock:
            return self._core.incrby(key, amount)

    async def scan(self, cursor: int = 0, match: Optional[str] = None, count: Optional[int] = None):
        async with self._lock:
            return self._core.scan(cursor, match, count)

    async def script_load(self, script: str) -> str:
        async with self._lock:
            return self._core.script_load(script)

    async def evalsha(self, sha: str, num_keys: int, *args) -> List[Any]:
        async with self._lock:
            return self._core.evalsha(sha, num_keys, *args)

    def pipeline(self):
        return InMemoryAsyncPipeline(self)


class InMemoryAsyncPipeline:
    def __init__(self, redis_client: InMemoryAsyncRedis):
        self._redis = redis_client
        self._ops: List[Tuple[str, Tuple[Any, ...]]] = []

    def incr(self, key: str, amount: int = 1):
        self._ops.append(("incrby", (key, amount)))
        return self

    def incrby(self, key: str, amount: int):
        self._ops.append(("incrby", (key, amount)))
        return self

    def expire(self, key: str, seconds: int):
        self._ops.append(("expire", (key, seconds)))
        return self

    async def execute(self):
        results = []
        for name, args in self._ops:
            method = getattr(self._redis, name)
            result = await method(*args)
            results.append(result)
        self._ops.clear()
        return results


class InMemorySyncRedis:
    """Synchronous wrapper around the in-memory Redis core."""

    def __init__(self, decode_responses: bool = True):
        self._core = _InMemoryRedisCore(decode_responses=decode_responses)
        self._lock = threading.Lock()

    def ping(self):
        with self._lock:
            return self._core.ping()

    def close(self):
        with self._lock:
            self._core.close()

    def pipeline(self):
        return InMemorySyncPipeline(self)

    # Expose subset of operations needed by the codebase
    def incr(self, key: str) -> int:
        with self._lock:
            return self._core.incr(key)

    def incrby(self, key: str, amount: int) -> int:
        with self._lock:
            return self._core.incrby(key, amount)

    def expire(self, key: str, seconds: int):
        with self._lock:
            self._core.expire(key, seconds)

    def get(self, key: str):
        with self._lock:
            return self._core.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None):
        with self._lock:
            self._core.set(key, value, ex=ex)

    def delete(self, key: str) -> int:
        with self._lock:
            return self._core.delete(key)


class InMemorySyncPipeline:
    def __init__(self, redis_client: InMemorySyncRedis):
        self._redis = redis_client
        self._ops: List[Tuple[str, Tuple[Any, ...]]] = []

    def incr(self, key: str, amount: int = 1):
        self._ops.append(("incrby", (key, amount)))
        return self

    def incrby(self, key: str, amount: int):
        self._ops.append(("incrby", (key, amount)))
        return self

    def expire(self, key: str, seconds: int):
        self._ops.append(("expire", (key, seconds)))
        return self

    def execute(self):
        results = []
        for name, args in self._ops:
            method = getattr(self._redis, name)
            results.append(method(*args))
        self._ops.clear()
        return results


async def ensure_async_client_closed(client) -> None:
    """
    Best-effort close for asyncio Redis clients (real or fake).
    """
    if client is None:
        return
    try:
        close = getattr(client, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result
    except Exception:
        pass


def ensure_sync_client_closed(client) -> None:
    """
    Best-effort close for synchronous Redis clients (real or fake).
    """
    if client is None:
        return
    try:
        close = getattr(client, "close", None)
        if close:
            close()
    except Exception:
        pass
