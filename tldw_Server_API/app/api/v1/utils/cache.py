"""
Caching and ETag helpers for API v1 endpoints.

Design goals:
- Stateless ETag calculation and If-None-Match handling that works
  even when Redis is disabled or unavailable.
- Optional Redis-backed response caching with TTL and basic
  per-media indexing to support targeted invalidation.
- Never surface Redis/cache errors directly to clients; treat
  failures as cache misses and log with context.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from typing import Any

from fastapi import Request
from loguru import logger

from tldw_Server_API.app.core.config import config
from tldw_Server_API.app.core.Infrastructure.redis_factory import create_sync_redis_client

CacheClient = Any  # Redis-like interface (setex/get/delete/sadd/smembers/expire/scan).


# TTL and enable flag come from central configuration.
CACHE_TTL: int = int(config.get("CACHE_TTL", 300))
_REDIS_ENABLED: bool = bool(config.get("REDIS_ENABLED", False))
_CACHE_CLIENT: CacheClient | None = None


def get_cache_client() -> CacheClient | None:
    """
    Return a Redis client when enabled and reachable, otherwise None.

    This function never raises; failures are logged and result in a
    disabled cache so callers can treat them as cache misses.
    """
    global _CACHE_CLIENT

    if not _REDIS_ENABLED:
        return None
    if _CACHE_CLIENT is not None:
        return _CACHE_CLIENT
    try:
        host = config.get("REDIS_HOST", None)
        port = config.get("REDIS_PORT", None)
        db = config.get("REDIS_DB", None)
        preferred_url = None
        if host and port is not None:
            db = db or 0
            preferred_url = f"redis://{host}:{int(port)}/{int(db)}"
        _CACHE_CLIENT = create_sync_redis_client(
            preferred_url=preferred_url,
            context="api_cache",
            fallback_to_fake=True,
            decode_responses=False,
        )
        logger.info("Redis cache enabled")
    except Exception as exc:  # pragma: no cover - defensive; logged once
        logger.warning(f"Failed to connect to Redis cache: {exc}. Running without cache.")
        _CACHE_CLIENT = None
    return _CACHE_CLIENT


def build_cache_key_from_request(
    request: Request,
    *,
    exclude_keys: Iterable[str] | None = None,
) -> str:
    """
    Build a stable cache key from the request URL and query params.

    - Excludes sensitive or highly-volatile query params (e.g., tokens).
    - Uses a hash of the parameter frozenset to avoid very long keys.
    """
    exclude = set(exclude_keys or ())
    # Always drop security tokens.
    exclude.update({"token"})
    params: MutableMapping[str, Any] = dict(request.query_params)
    for key in exclude:
        params.pop(key, None)
    frozen = frozenset(params.items())
    return f"cache:{request.url.path}:{hash(frozen)}"


def build_cache_key(
    path: str,
    query_params: Mapping[str, Any],
    *,
    exclude_keys: Iterable[str] | None = None,
) -> str:
    """
    Build a stable cache key from path and query parameters.

    This mirrors :func:`build_cache_key_from_request` but works with
    plain mappings for easier unit testing.
    """
    exclude = set(exclude_keys or ())
    exclude.update({"token"})
    params: dict[str, Any] = {k: v for k, v in query_params.items() if k not in exclude}
    frozen = frozenset(params.items())
    return f"cache:{path}:{hash(frozen)}"


def _serialize_for_etag(payload: Any) -> str:
    """
    Deterministically serialize payload for ETag generation.

    - Uses sorted keys and compact separators.
    - Falls back to ``str(obj)`` for non-JSON-serializable values.
    """
    def _default(obj: Any) -> Any:
        try:
            return str(obj)
        except Exception:
            return repr(obj)

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=_default,
    )


def generate_etag(payload: Any) -> str:
    """
    Generate a strong ETag for the given payload.

    The ETag is a hex MD5 of a deterministic JSON serialization.
    """
    serialized = _serialize_for_etag(payload)
    return hashlib.md5(serialized.encode("utf-8")).hexdigest()


def parse_if_none_match(header_value: str | None) -> Sequence[str]:
    """
    Parse an If-None-Match header into a list of candidate ETags.

    Handles common forms:
    - \"etag\"
    - W/\"etag\"
    - etag, \"etag2\"
    """
    if not header_value:
        return []
    raw_tokens = [t.strip() for t in header_value.split(",") if t.strip()]
    etags: list[str] = []
    for token in raw_tokens:
        if token.startswith("W/"):
            token = token[2:].strip()
        if token.startswith('"') and token.endswith('"') and len(token) >= 2:
            token = token[1:-1]
        if token:
            etags.append(token)
    return etags


def is_not_modified(current_etag: str, if_none_match: str | None) -> bool:
    """
    Return True when the provided If-None-Match header matches current_etag.
    """
    return current_etag in parse_if_none_match(if_none_match)


def cache_response(
    key: str,
    payload: Any,
    *,
    client: CacheClient | None = None,
    media_id: int | None = None,
) -> str:
    """
    Cache a response payload under the given key and return its ETag.

    - If no cache client is available, this is a no-op beyond ETag calculation.
    - When a media_id is provided, an index set is maintained to support
      targeted invalidation.
    """
    etag = generate_etag(payload)
    cache = client or get_cache_client()
    if cache is None:
        return etag
    try:
        serialized = _serialize_for_etag(payload)
        cache.setex(key, CACHE_TTL, f"{etag}|{serialized}")
        if media_id is not None:
            try:
                idx_key = f"cacheidx:/api/v1/media/{int(media_id)}"
                cache.sadd(idx_key, key)
                cache.expire(idx_key, max(CACHE_TTL, 300))
            except Exception:  # pragma: no cover - defensive
                pass
    except Exception as exc:  # pragma: no cover - defensive; avoid breaking handlers
        logger.warning(f"Failed to cache response for key '{key}': {exc}")
    return etag


def get_cached_response(
    key: str,
    *,
    client: CacheClient | None = None,
) -> tuple[str, Any] | None:
    """
    Retrieve a cached payload and its ETag for the given key.

    Returns ``None`` on cache miss or when cache is disabled.
    """
    cache = client or get_cache_client()
    if cache is None:
        return None
    try:
        cached_value = cache.get(key)
        if not cached_value:
            return None
        if isinstance(cached_value, bytes):
            decoded = cached_value.decode("utf-8")
        else:
            decoded = str(cached_value)
        parts = decoded.split("|", 1)
        if len(parts) != 2:
            logger.warning(f"Cached value for key '{key}' has unexpected format")
            return None
        etag, content_str = parts
        try:
            payload = json.loads(content_str)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode cached JSON for key '{key}'")
            return None
        return etag, payload
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Failed to retrieve cached response for key '{key}': {exc}")
        return None


def invalidate_media_cache(
    media_id: int,
    *,
    client: CacheClient | None = None,
) -> None:
    """
    Invalidate cache entries related to a specific media item.

    Strategy:
    - Prefer O(1) set-based invalidation via ``cacheidx:/api/v1/media/{id}``.
    - Fall back to SCAN-based deletion of keys matching the path pattern.
    """
    cache = client or get_cache_client()
    if cache is None:
        return
    try:
        idx_key = f"cacheidx:/api/v1/media/{int(media_id)}"
        keys: list[Any] = []
        try:
            members = cache.smembers(idx_key)
            if members:
                keys = list(members)
        except Exception:
            keys = []

        total_deleted = 0
        if keys:
            try:
                total_deleted += cache.delete(*keys)
            except Exception:
                for key in keys:
                    try:
                        cache.delete(key)
                        total_deleted += 1
                    except Exception:
                        pass
            try:
                cache.delete(idx_key)
            except Exception:
                pass

        # Fallback: scan for keys matching the media path.
        pattern = f"cache:/api/v1/media/{int(media_id)}:*"
        cursor = 0
        while True:
            try:
                cursor, scan_keys = cache.scan(cursor=cursor, match=pattern, count=500)
            except Exception:
                break
            if scan_keys:
                try:
                    total_deleted += cache.delete(*scan_keys)
                except Exception:
                    for key in scan_keys:
                        try:
                            cache.delete(key)
                            total_deleted += 1
                        except Exception:
                            pass
            if cursor == 0:
                break
        if total_deleted:
            logger.info(f"Invalidated {total_deleted} cache entries for media ID {media_id}")
        else:
            logger.debug(f"No cached entries found to invalidate for media ID {media_id}")
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(f"Unexpected error invalidating cache for media ID {media_id}: {exc}")


__all__ = [
    "CACHE_TTL",
    "CacheClient",
    "build_cache_key",
    "build_cache_key_from_request",
    "generate_etag",
    "get_cache_client",
    "get_cached_response",
    "invalidate_media_cache",
    "is_not_modified",
    "parse_if_none_match",
    "cache_response",
]
