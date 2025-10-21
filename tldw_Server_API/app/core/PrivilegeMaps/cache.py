from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional

from fastapi.encoders import jsonable_encoder
from loguru import logger

from tldw_Server_API.app.core.Infrastructure.redis_factory import create_sync_redis_client
from tldw_Server_API.app.core.RAG.rag_service.advanced_cache import MemoryCache
from tldw_Server_API.app.core.Metrics import get_metrics_registry


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() not in {"0", "false", "no", "off", ""}


class DistributedPrivilegeCache:
    """
    Lightweight distributed cache for privilege summaries.

    Provides in-process caching with optional Redis persistence and invalidation broadcasts.
    """

    def __init__(self, namespace: Optional[str] = None) -> None:
        self._namespace = (namespace or os.getenv("PRIVILEGE_CACHE_NAMESPACE") or "privmap").strip()
        self._local = MemoryCache()
        self._backend_name = (os.getenv("PRIVILEGE_CACHE_BACKEND", "memory") or "memory").strip().lower()
        self._redis = None
        self._redis_ttl: Optional[int] = None
        self._sliding_ttl = _truthy(os.getenv("PRIVILEGE_CACHE_SLIDING_TTL", "1"))
        self._generation: int = 0
        self._last_generation_sync: float = 0.0
        self._generation_poll_interval = max(
            0.5,
            float(os.getenv("PRIVILEGE_CACHE_GENERATION_SYNC_SECONDS", "2") or "2"),
        )
        self._pubsub = None
        self._pubsub_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        if self._backend_name == "redis":
            self._redis = self._create_redis_client()
            if self._redis is None:
                self._backend_name = "memory"

        self._metrics = None
        self._metrics_labels: Dict[str, str] = {}
        self._init_metrics()

        if self._redis is not None:
            self._bootstrap_generation()
            self._start_pubsub_listener()
        else:
            self._set_generation_gauge()
        self._update_entry_gauge()

    def get(self, key: str) -> Optional[Any]:
        self._sync_generation()
        value = self._local.get(key)
        if value is not None:
            self._record_hit(layer="local")
            return value
        self._record_miss(layer="local")
        if self._redis is None:
            return None
        redis_key = self._redis_key(key)
        try:
            payload = self._redis.get(redis_key)
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.debug("Privilege cache redis get failed: %s", exc)
            self._record_miss(layer="backend")
            return None
        if not payload:
            self._record_miss(layer="backend")
            return None
        try:
            parsed = json.loads(payload)
            decoded = parsed.get("payload", parsed)
            redis_ttl = parsed.get("ttl")
            if redis_ttl is not None:
                try:
                    self._redis_ttl = int(redis_ttl)
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Privilege cache redis payload decode failed: %s", exc)
            self._record_miss(layer="backend")
            return None
        if self._sliding_ttl and self._redis_ttl and self._redis_ttl > 0:
            try:
                self._redis.expire(redis_key, self._redis_ttl)
            except Exception:
                pass
        if isinstance(decoded, dict) and decoded.get("__cached_ts"):
            decoded.pop("__cached_ts", None)
        self._local.set(key, decoded, ttl_sec=self._redis_ttl)
        self._record_hit(layer="backend")
        self._update_entry_gauge()
        return decoded

    def set(self, key: str, value: Any, ttl_sec: Optional[int] = None) -> None:
        self._redis_ttl = ttl_sec
        self._local.set(key, value, ttl_sec=ttl_sec)
        self._update_entry_gauge()
        if self._redis is None:
            return
        payload = {
            "payload": jsonable_encoder(value),
            "ttl": ttl_sec if ttl_sec is not None else None,
            "__cached_ts": time.time(),
        }
        redis_key = self._redis_key(key)
        try:
            if ttl_sec and ttl_sec > 0:
                self._redis.setex(redis_key, ttl_sec, json.dumps(payload, separators=(",", ":")))
            else:
                self._redis.set(redis_key, json.dumps(payload, separators=(",", ":")))
        except Exception as exc:  # pragma: no cover - best-effort logging
            logger.debug("Privilege cache redis set failed: %s", exc)

    def invalidate(self) -> None:
        """Clear local cache and broadcast invalidation to peer workers."""
        self._local.clear()
        self._update_entry_gauge()
        if self._redis is None:
            self._generation += 1
            self._set_generation_gauge()
            self._record_invalidation()
            return
        try:
            new_generation = self._redis.incr(self._generation_key())
            self._generation = int(new_generation)
        except Exception as exc:
            logger.debug("Privilege cache generation increment failed: %s", exc)
        try:
            channel = self._invalidate_channel()
            self._redis.publish(channel, str(self._generation))
        except Exception:
            # Publish is best-effort; fallback generation polling covers rest.
            pass
        self._set_generation_gauge()
        self._record_invalidation()

    def close(self) -> None:
        """Stop background workers."""
        self._stop_event.set()
        if self._pubsub is not None:
            try:
                self._pubsub.close()
            except Exception:
                pass
        if self._pubsub_thread and self._pubsub_thread.is_alive():
            self._pubsub_thread.join(timeout=0.5)
        self._pubsub_thread = None
        self._pubsub = None

    @property
    def generation(self) -> int:
        self._sync_generation()
        return self._generation

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _create_redis_client(self):
        try:
            return create_sync_redis_client(
                preferred_url=os.getenv("PRIVILEGE_CACHE_REDIS_URL"),
                context="privilege_maps_cache",
                fallback_to_fake=True,
                decode_responses=True,
            )
        except Exception as exc:
            logger.warning("Unable to initialize privilege cache redis client: %s", exc)
            return None

    def _bootstrap_generation(self) -> None:
        try:
            raw = self._redis.get(self._generation_key())
            if raw is None:
                self._redis.set(self._generation_key(), "0")
                self._generation = 0
            else:
                self._generation = int(raw)
        except Exception as exc:
            logger.debug("Privilege cache generation bootstrap failed: %s", exc)
        self._set_generation_gauge()

    def _sync_generation(self, force: bool = False) -> None:
        if self._redis is None:
            return
        now = time.time()
        if not force and (now - self._last_generation_sync) < self._generation_poll_interval:
            return
        try:
            raw = self._redis.get(self._generation_key())
            if raw is None:
                self._generation = 0
            else:
                remote_generation = int(raw)
                if remote_generation != self._generation:
                    self._generation = remote_generation
                    self._local.clear()
                    self._update_entry_gauge()
        except Exception as exc:
            logger.debug("Privilege cache generation sync failed: %s", exc)
        finally:
            self._last_generation_sync = now
            self._set_generation_gauge()

    def _start_pubsub_listener(self) -> None:
        if self._redis is None:
            return
        if not hasattr(self._redis, "pubsub"):
            return
        try:
            self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
            channel = self._invalidate_channel()
            self._pubsub.subscribe(channel)
        except Exception as exc:
            logger.debug("Privilege cache pubsub subscribe failed: %s", exc)
            self._pubsub = None
            return

        def _listen() -> None:
            if self._pubsub is None:
                return
            try:
                for message in self._pubsub.listen():
                    if self._stop_event.is_set():
                        break
                    if not message or message.get("type") != "message":
                        continue
                    data = message.get("data")
                    try:
                        new_generation = int(data)
                    except Exception:
                        new_generation = None
                    self._local.clear()
                    self._update_entry_gauge()
                    if new_generation is not None:
                        self._generation = new_generation
                        self._set_generation_gauge()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("Privilege cache pubsub listener exited: %s", exc)

        self._pubsub_thread = threading.Thread(target=_listen, name="privmap-cache-pubsub", daemon=True)
        self._pubsub_thread.start()

    def _generation_key(self) -> str:
        return f"{self._namespace}:generation"

    def _invalidate_channel(self) -> str:
        return f"{self._namespace}:invalidate"

    def _redis_key(self, key: str) -> str:
        return f"{self._namespace}:summary:{key}"

    def _init_metrics(self) -> None:
        try:
            registry = get_metrics_registry()
        except Exception:  # pragma: no cover - metrics optional
            self._metrics = None
            self._metrics_labels = {}
            return
        self._metrics = registry
        self._metrics_labels = {"backend": self._resolve_backend_label()}

    def _resolve_backend_label(self) -> str:
        if self._backend_name == "redis":
            if self._redis is None:
                return "memory"
            cls_name = self._redis.__class__.__name__
            if "InMemory" in cls_name:
                return "redis_stub"
            return "redis"
        return "memory"

    def _record_hit(self, *, layer: str) -> None:
        if not self._metrics:
            return
        labels = dict(self._metrics_labels)
        labels["layer"] = layer
        try:
            self._metrics.increment("privilege_cache_hits_total", 1, labels)
        except Exception:  # pragma: no cover - defensive
            pass

    def _record_miss(self, *, layer: str) -> None:
        if not self._metrics:
            return
        labels = dict(self._metrics_labels)
        labels["layer"] = layer
        try:
            self._metrics.increment("privilege_cache_misses_total", 1, labels)
        except Exception:  # pragma: no cover - defensive
            pass

    def _record_invalidation(self) -> None:
        if not self._metrics:
            return
        try:
            self._metrics.increment("privilege_cache_invalidations_total", 1, self._metrics_labels)
        except Exception:  # pragma: no cover
            pass

    def _set_generation_gauge(self) -> None:
        if not self._metrics:
            return
        try:
            self._metrics.set_gauge("privilege_cache_generation", float(self._generation), self._metrics_labels)
        except Exception:  # pragma: no cover
            pass

    def _update_entry_gauge(self) -> None:
        if not self._metrics:
            return
        size = 0
        try:
            store = getattr(self._local, "_store", {})
            size = len(store)
        except Exception:
            size = 0
        try:
            self._metrics.set_gauge("privilege_cache_entries", float(size), self._metrics_labels)
        except Exception:  # pragma: no cover
            pass


_GLOBAL_CACHE: Optional[DistributedPrivilegeCache] = None


def get_privilege_cache() -> DistributedPrivilegeCache:
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is None:
        _GLOBAL_CACHE = DistributedPrivilegeCache()
    return _GLOBAL_CACHE


def invalidate_privilege_cache() -> None:
    get_privilege_cache().invalidate()


def reset_privilege_cache() -> None:
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is not None:
        try:
            _GLOBAL_CACHE.close()
        except Exception:
            pass
    _GLOBAL_CACHE = None
