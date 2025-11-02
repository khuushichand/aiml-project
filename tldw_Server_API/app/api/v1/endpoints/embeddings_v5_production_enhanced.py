# embeddings_v5_production_enhanced.py
# Enhanced version with circuit breaker pattern and improved error recovery
"""
Production-ready OpenAI-compatible embeddings API with circuit breaker.

Key enhancements over v5:
- Circuit breaker pattern for fault tolerance
- Improved connection cleanup on failures
- Better error recovery mechanisms
- Enhanced monitoring and observability
"""

from __future__ import annotations

import asyncio
import inspect
import json
import base64
import hashlib
import time
import threading
from datetime import datetime, timedelta
from typing import List, Union, Optional, Dict, Any, Tuple
from enum import Enum
import numpy as np
from functools import lru_cache, wraps
import atexit
import os

from fastapi import APIRouter, HTTPException, Body, Depends, status, BackgroundTasks, Request, Query, Header, Response
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse, StreamingResponse
import tiktoken
from loguru import logger
from asyncio import Lock
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Schemas
from tldw_Server_API.app.api.v1.schemas.embeddings_models import (
    CreateEmbeddingRequest,
    CreateEmbeddingResponse,
    EmbeddingData,
    EmbeddingUsage
)
from tldw_Server_API.app.core.Usage.usage_tracker import log_llm_usage
from pydantic import BaseModel, Field

# Authentication
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, ensure_traceparent, get_ps_logger
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode

# Configuration
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.config import load_comprehensive_config
from pathlib import Path
import configparser

# Audit logging: unify later via unified audit DI; legacy import removed (unused here)
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager

# Circuit Breaker
from tldw_Server_API.app.core.Embeddings.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    circuit_breaker,
    registry as circuit_breaker_registry
)

# Rate limiting
from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import limiter

# Monitoring
from prometheus_client import Counter, Histogram, Gauge
import redis.asyncio as aioredis
from tldw_Server_API.app.core.Infrastructure.redis_factory import (
    create_async_redis_client,
    ensure_async_client_closed,
)
from tldw_Server_API.app.core.Embeddings.dlq_crypto import decrypt_payload_if_present
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType, AuditEventCategory
from fnmatch import fnmatch

# ============================================================================
# Embeddings Implementation Import (Safe/Lazy)
# Avoid hard-failing on import so non-embedding tests can import the app.
# ============================================================================

try:
    from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
        EmbeddingConfigSchema,
        HFModelCfg,
        ONNXModelCfg,
        OpenAIModelCfg,
        LocalAPICfg,
        create_embeddings_batch,
        resolve_model_storage_base_dir,
    )
    EMBEDDINGS_AVAILABLE = True
except Exception as e:
    # Do not raise here; allow the API to import and mark the embeddings service as unavailable.
    logger.error(f"Embeddings implementation unavailable: {e}")
    logger.error("Embeddings endpoints will respond 503 until dependencies are installed")
    EMBEDDINGS_AVAILABLE = False

    def resolve_model_storage_base_dir(*_args, **_kwargs):
        return "./models/embedding_models_data/"

from tldw_Server_API.app.core.Embeddings.request_batching import (
    create_embeddings_batch_async as batching_create_embeddings_batch_async,
)

# ============================================================================
# Metrics and Monitoring
# ============================================================================

from prometheus_client import REGISTRY

# Safely get or create metrics
def get_or_create_counter(name, description, labelnames):
    """Get existing counter or create new one"""
    try:
        # Check if metric already exists
        if name in REGISTRY._names_to_collectors:
            collector = REGISTRY._names_to_collectors[name]
            # Verify it's a Counter with matching labels
            if hasattr(collector, '_labelnames') and set(collector._labelnames) == set(labelnames):
                return collector
            # If labels don't match, unregister the old one
            REGISTRY.unregister(collector)
        return Counter(name, description, labelnames)
    except Exception as e:
        # Try to create new counter, handling any registration issues
        try:
            return Counter(name, description, labelnames)
        except Exception:
            # Return existing if we can't create new
            if name in REGISTRY._names_to_collectors:
                return REGISTRY._names_to_collectors[name]
            raise

def get_or_create_histogram(name, description, labelnames):
    """Get existing histogram or create new one"""
    try:
        if name in REGISTRY._names_to_collectors:
            collector = REGISTRY._names_to_collectors[name]
            # Verify it's a Histogram with matching labels
            if hasattr(collector, '_labelnames') and set(collector._labelnames) == set(labelnames):
                return collector
            # If labels don't match, unregister the old one
            REGISTRY.unregister(collector)
        return Histogram(name, description, labelnames)
    except Exception:
        # Try to create new, or return existing
        try:
            return Histogram(name, description, labelnames)
        except Exception:
            if name in REGISTRY._names_to_collectors:
                return REGISTRY._names_to_collectors[name]
            raise

def get_or_create_gauge(name, description, labelnames=None):
    """Get existing gauge or create new one"""
    try:
        if name in REGISTRY._names_to_collectors:
            collector = REGISTRY._names_to_collectors[name]
            expected_labels = set(labelnames) if labelnames else set()
            existing_labels = set(collector._labelnames) if hasattr(collector, '_labelnames') else set()
            if expected_labels == existing_labels:
                return collector
            # If labels don't match, unregister the old one
            REGISTRY.unregister(collector)
        if labelnames:
            return Gauge(name, description, labelnames)
        return Gauge(name, description)
    except Exception:
        # Try to create new, or return existing
        try:
            if labelnames:
                return Gauge(name, description, labelnames)
            return Gauge(name, description)
        except Exception:
            if name in REGISTRY._names_to_collectors:
                return REGISTRY._names_to_collectors[name]
            raise

# Create metrics using safe getters
embedding_requests_total = get_or_create_counter(
    'embedding_requests_total',
    'Total number of embedding requests',
    ['provider', 'model', 'status']
)

embedding_request_duration = get_or_create_histogram(
    'embedding_request_duration_seconds',
    'Duration of embedding requests',
    ['provider', 'model']
)

embedding_cache_hits = get_or_create_counter(
    'embedding_cache_hits_total',
    'Number of cache hits',
    ['provider', 'model']
)

embedding_cache_size = get_or_create_gauge(
    'embedding_cache_size',
    'Current size of embedding cache'
)

active_embedding_requests = get_or_create_gauge(
    'active_embedding_requests',
    'Number of active embedding requests'
)

# Additional observability counters
embedding_provider_failures = get_or_create_counter(
    'embedding_provider_failures_total',
    'Provider failures by reason',
    ['provider', 'model', 'reason']
)

embedding_fallbacks_total = get_or_create_counter(
    'embedding_fallbacks_total',
    'Count of provider fallbacks taken',
    ['from_provider', 'to_provider']
)

embedding_policy_denied_total = get_or_create_counter(
    'embedding_policy_denied_total',
    'Requests denied by policy',
    ['provider', 'model', 'policy_type']
)

embedding_dimension_adjustments_total = get_or_create_counter(
    'embedding_dimension_adjustments_total',
    'Count of dimension adjustments performed',
    ['provider', 'model', 'method']
)

embedding_token_inputs_total = get_or_create_counter(
    'embedding_token_inputs_total',
    'Number of requests using token array inputs',
    ['mode']  # single or batch
)

# DLQ/admin metrics
dlq_requeued_total = get_or_create_counter(
    'embedding_dlq_requeued_total',
    'Number of DLQ items requeued via admin API',
    ['queue_name', 'status']
)
dlq_requeue_errors_total = get_or_create_counter(
    'embedding_dlq_requeue_errors_total',
    'Errors during DLQ requeue operations',
    ['queue_name', 'error_type']
)

# Orchestrator observability metrics
orchestrator_sse_connections = get_or_create_gauge(
    'orchestrator_sse_connections',
    'Current number of active SSE connections to orchestrator'
)

orchestrator_sse_disconnects_total = get_or_create_counter(
    'orchestrator_sse_disconnects_total',
    'Total number of SSE disconnect events from orchestrator',
    []
)

orchestrator_summary_failures_total = get_or_create_counter(
    'orchestrator_summary_failures_total',
    'Total number of summary failures (fallbacks returned)',
    []
)

# Export queue age and stage flags for Prometheus scraping
embedding_queue_age_current_seconds = get_or_create_gauge(
    'embedding_queue_age_current_seconds',
    'Current age (seconds) of oldest message per queue',
    ['queue_name']
)

embedding_stage_flag = get_or_create_gauge(
    'embedding_stage_flag',
    'Per-stage control flags as gauges (1=true,0=false)',
    ['stage', 'flag']
)

## Backpressure and quotas (configured later; depends on _cfg_int defined below)

# ============================================================================
# Configuration and Constants
# ============================================================================

class EmbeddingProvider(str, Enum):
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    ONNX = "onnx"
    LOCAL_API = "local_api"
    COHERE = "cohere"
    VOYAGE = "voyage"
    GOOGLE = "google"
    MISTRAL = "mistral"

# Production configuration
DEFAULT_MAX_BATCH_SIZE = 100
DEFAULT_MAX_CACHE_SIZE = 5000
DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_CACHE_CLEANUP_INTERVAL = 300
DEFAULT_CONNECTION_POOL_SIZE = 20
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3

# Allow overriding via settings/env
def _cfg_int(name: str, default_val: int) -> int:
    try:
        from tldw_Server_API.app.core.config import settings as _settings
        val = _settings.get(name, None)
        if isinstance(val, (int, float)):
            return int(val)
    except Exception:
        pass
    try:
        env = os.getenv(name)
        if env is not None and str(env).strip() != "":
            return int(env)
    except Exception:
        pass
    return default_val

# Backpressure and quotas configuration
def _cfg_float(name: str, default_val: float) -> float:
    try:
        v = settings.get(name, None)
        if isinstance(v, (int, float)):
            return float(v)
    except Exception:
        pass
    try:
        env = os.getenv(name)
        if env is not None and str(env).strip() != "":
            return float(env)
    except Exception:
        pass
    return float(default_val)

BP_MAX_DEPTH = int(_cfg_int("EMB_BACKPRESSURE_MAX_DEPTH", 25000))
BP_MAX_AGE_S = _cfg_float("EMB_BACKPRESSURE_MAX_AGE_SECONDS", 300.0)
TENANT_RPS = int(_cfg_int("EMBEDDINGS_TENANT_RPS", 0))  # 0 disables
# Orchestrator snapshot scan cap (prevent unbounded SCAN work per build)
ORCH_SCAN_MAX_KEYS = int(_cfg_int("EMB_ORCH_MAX_SCAN_KEYS", 500))

async def _orchestrator_depth_and_age(client: aioredis.Redis) -> tuple[int, float]:
    """Return (max_queue_depth, max_queue_age_seconds) for core embeddings queues."""
    queues = ["embeddings:chunking", "embeddings:embedding", "embeddings:storage"]
    depths = []
    ages = []
    now = time.time()
    for q in queues:
        try:
            d = await client.xlen(q)
        except Exception:
            d = 0
        depths.append(int(d or 0))
        try:
            items = await client.xrange(q, "-", "+", count=1)
            if items:
                first_id = items[0][0]
                ts_ms = float(first_id.split("-", 1)[0])
                ages.append(max(0.0, now - (ts_ms / 1000.0)))
            else:
                ages.append(0.0)
        except Exception:
            ages.append(0.0)
    return (max(depths) if depths else 0, max(ages) if ages else 0.0)

async def _check_backpressure_and_quotas(request: Request, user: User) -> Optional[HTTPException]:
    """Return HTTPException(429) if backpressure or tenant quota exceeded; else None."""
    # Orchestrator-based backpressure
    try:
        client = await _get_redis_client()
    except Exception:
        client = None
    try:
        if client is not None:
            depth, age = await _orchestrator_depth_and_age(client)
            if depth >= BP_MAX_DEPTH or age >= BP_MAX_AGE_S:
                retry_after = 5
                if age >= BP_MAX_AGE_S:
                    retry_after = min(60, int(max(5, age / 2)))
                headers = {"Retry-After": str(retry_after)}
                return HTTPException(status_code=429, detail="Backpressure: queue overload", headers=headers)
    except Exception:
        pass
    finally:
        try:
            if client is not None:
                    await ensure_async_client_closed(client)
        except Exception:
            pass

    # Per-tenant quotas in multi-user mode
    try:
        def _is_multi_user_runtime() -> bool:
            try:
                am = os.getenv("AUTH_MODE")
                if am:
                    return am.strip().lower() == "multi_user"
            except Exception:
                pass
            try:
                return not is_single_user_mode()
            except Exception:
                return False

        # Read tenant RPS dynamically so tests can monkeypatch env at runtime
        def _tenant_rps_runtime() -> int:
            try:
                # Prefer env var when set during tests; fall back to settings
                env_val = os.getenv("EMBEDDINGS_TENANT_RPS")
                if env_val is not None and str(env_val).strip() != "":
                    return int(env_val)
            except Exception:
                pass
            try:
                v = settings.get("EMBEDDINGS_TENANT_RPS", 0)
                if isinstance(v, (int, float)):
                    return int(v)
            except Exception:
                pass
            # Fallback to module default
            return TENANT_RPS

        tenant_rps = _tenant_rps_runtime()

        if _is_multi_user_runtime() and tenant_rps > 0:
            client2 = await _get_redis_client()
            try:
                # Use a single rolling key with 1-second TTL to avoid flakiness across second boundaries
                key = f"embeddings:tenant:rps:{getattr(user, 'id', 'anon')}"
                current = await client2.incr(key)
                # Ensure expiry of 1 second for a strict RPS window
                await client2.expire(key, 1)
                remaining = max(0, tenant_rps - int(current or 0))
                if current > tenant_rps:
                    headers = {"Retry-After": "1", "X-RateLimit-Limit": str(tenant_rps), "X-RateLimit-Remaining": str(0)}
                    return HTTPException(status_code=429, detail="Tenant quota exceeded", headers=headers)
                else:
                    if hasattr(request, 'state'):
                        try:
                            request.state.rate_limit_limit = tenant_rps
                            request.state.rate_limit_remaining = remaining
                        except Exception:
                            pass
            finally:
                try:
                    await ensure_async_client_closed(client2)
                except Exception:
                    pass
    except Exception:
        pass
    return None


# ============================================================================
# Redis helpers for DLQ admin endpoints
# ============================================================================

async def _get_redis_client() -> aioredis.Redis:
    return await create_async_redis_client(context="embeddings_api")

def _dlq_stream_name(stage: str) -> str:
    stage = stage.strip().lower()
    if stage not in {"chunking", "embedding", "storage"}:
        raise HTTPException(status_code=400, detail="Invalid stage; must be one of chunking|embedding|storage")
    return f"embeddings:{stage}:dlq"

def _live_stream_name(stage: str) -> str:
    stage = stage.strip().lower()
    if stage not in {"chunking", "embedding", "storage"}:
        raise HTTPException(status_code=400, detail="Invalid stage; must be one of chunking|embedding|storage")
    return f"embeddings:{stage}"

MAX_BATCH_SIZE = _cfg_int("EMBEDDINGS_MAX_BATCH_SIZE", DEFAULT_MAX_BATCH_SIZE)
MAX_CACHE_SIZE = _cfg_int("EMBEDDINGS_CACHE_MAX_SIZE", DEFAULT_MAX_CACHE_SIZE)
CACHE_TTL_SECONDS = _cfg_int("EMBEDDINGS_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS)
CACHE_CLEANUP_INTERVAL = _cfg_int("EMBEDDINGS_CACHE_CLEANUP_INTERVAL", DEFAULT_CACHE_CLEANUP_INTERVAL)
CONNECTION_POOL_SIZE = _cfg_int("EMBEDDINGS_CONNECTION_POOL_SIZE", DEFAULT_CONNECTION_POOL_SIZE)
REQUEST_TIMEOUT = _cfg_int("EMBEDDINGS_REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT)
MAX_RETRIES = _cfg_int("EMBEDDINGS_MAX_RETRIES", DEFAULT_MAX_RETRIES)

# Circuit breaker configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60
CIRCUIT_BREAKER_SUCCESS_THRESHOLD = 2

# Provider models configuration
PROVIDER_MODELS = {
    EmbeddingProvider.OPENAI: [
        "text-embedding-ada-002",
        "text-embedding-3-small",
        "text-embedding-3-large"
    ],
    EmbeddingProvider.COHERE: [
        "embed-english-v3.0",
        "embed-multilingual-v3.0"
    ],
    EmbeddingProvider.HUGGINGFACE: [
        "sentence-transformers/all-MiniLM-L6-v2",
        "sentence-transformers/all-mpnet-base-v2",
        "intfloat/multilingual-e5-large-instruct",
        "Qwen/Qwen3-Embedding-0.6B",
        # Newly added supported models
        "NovaSearch/stella_en_1.5B_v5",
        "NovaSearch/stella_en_400M_v5",
        "jinaai/jina-embeddings-v4",
        "intfloat/multilingual-e5-large",
        "mixedbread-ai/mxbai-embed-large-v1",
        "jinaai/jina-embeddings-v3",
        "BAAI/bge-large-en-v1.5",
        "BAAI/bge-small-en-v1.5",
    ]
}

# Optional allowlists and per-model token limits (override via settings)
def _get_allowed_providers() -> Optional[List[str]]:
    try:
        vals = settings.get("ALLOWED_EMBEDDING_PROVIDERS", [])
        if isinstance(vals, list) and vals:
            return [str(v).lower() for v in vals]
    except Exception:
        pass
    return None


def _chroma_manager_for_user(user: User) -> ChromaDBManager:
    cfg = settings.get("EMBEDDING_CONFIG", {}).copy()
    cfg["USER_DB_BASE_DIR"] = settings.get("USER_DB_BASE_DIR")
    user_id = getattr(user, "id", None) or settings.get("SINGLE_USER_FIXED_ID", "1")
    return ChromaDBManager(user_id=str(user_id), user_embedding_config=cfg)


def _resolve_model_and_provider(model: Optional[str], provider: Optional[str]) -> Tuple[str, str]:
    cfg = settings.get("EMBEDDING_CONFIG", {}) or {}
    default_model = model or cfg.get("embedding_model") or cfg.get("default_model_id") or "sentence-transformers/all-MiniLM-L6-v2"
    resolved_provider = guess_provider_for_model(default_model, provider)
    return default_model, resolved_provider


def _get_allowed_models() -> Optional[List[str]]:
    try:
        vals = settings.get("ALLOWED_EMBEDDING_MODELS", [])
        if isinstance(vals, list) and vals:
            return [str(v) for v in vals]
    except Exception:
        pass
    return None

def _get_model_max_tokens(provider: str, model: str) -> int:
    # Settings-driven override map: {"provider:model": max_tokens} or {"model": max_tokens}
    try:
        mapping = settings.get("EMBEDDING_MODEL_MAX_TOKENS", {}) or {}
        key1 = f"{provider}:{model}"
        if key1 in mapping:
            return int(mapping[key1])
        if model in mapping:
            return int(mapping[model])
    except Exception:
        pass
    # Reasonable defaults
    if provider == "openai":
        return 8192
    # Default for HF/local_api/others if not configured
    return 8192


def _build_user_metadata(user: Optional[User]) -> Optional[Dict[str, Any]]:
    """Create metadata dict for rate limiter propagation.

    In test contexts (TESTING=true), skip attaching user metadata so that
    the embeddings batcher does not apply rate limiting during tests.
    """
    try:
        # Bypass rate limiting propagation in tests
        if str(os.getenv("TESTING", "")).lower() in {"1", "true", "yes", "on"}:
            return None
        if user is None:
            return None
        user_id = getattr(user, "id", None)
        if user_id is None:
            return None
        return {"user_id": str(user_id)}
    except Exception:
        return None

# ============================================================================
# Enhanced TTL Cache with Better Cleanup
# ============================================================================

class TTLCache:
    """Thread-safe cache with TTL support and automatic cleanup"""

    def __init__(self, max_size: int = MAX_CACHE_SIZE, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.cleanup_task = None
        # Optional daemon-thread cleanup to decouple from app loop
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_stop: Optional[threading.Event] = None
        try:
            self._use_thread = str(os.getenv("EMBEDDINGS_TTLCACHE_DAEMON", "true")).lower() in ("1", "true", "yes", "on")
        except Exception:
            self._use_thread = True
        self.hits = 0
        self.misses = 0

    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self._use_thread:
            # Start daemon thread once
            if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
                self._cleanup_stop = threading.Event()

                def _runner():
                    try:
                        while self._cleanup_stop and not self._cleanup_stop.is_set():
                            try:
                                self._cleanup_expired_locked()
                            except Exception:
                                pass
                            if self._cleanup_stop:
                                self._cleanup_stop.wait(CACHE_CLEANUP_INTERVAL)
                            else:
                                time.sleep(CACHE_CLEANUP_INTERVAL)
                    except Exception:
                        pass

                self._cleanup_thread = threading.Thread(
                    target=_runner,
                    name="embeddings-ttlcache",
                    daemon=True,
                )
                self._cleanup_thread.start()
        else:
            if self.cleanup_task is None:
                self.cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self._use_thread:
            try:
                if self._cleanup_stop:
                    self._cleanup_stop.set()
                # No need to join daemon thread during interpreter teardown, but attempt a brief join
                if self._cleanup_thread and self._cleanup_thread.is_alive():
                    self._cleanup_thread.join(timeout=0.5)
            except Exception:
                pass
            finally:
                self._cleanup_thread = None
                self._cleanup_stop = None
        else:
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
                self.cleanup_task = None

    async def _cleanup_loop(self):
        """Background task to clean up expired entries"""
        while True:
            try:
                await asyncio.sleep(CACHE_CLEANUP_INTERVAL)
                self._cleanup_expired_locked()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")

    def _cleanup_expired_locked(self):
        """Remove expired entries under the cache lock."""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, value in self.cache.items()
                if current_time - value['timestamp'] > self.ttl_seconds
            ]

            for key in expired_keys:
                del self.cache[key]

            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                embedding_cache_size.set(len(self.cache))

    async def cleanup_expired(self):
        """Async wrapper for cache cleanup."""
        self._cleanup_expired_locked()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        with self._lock:
            entry = self.cache.get(key)
            if entry is None:
                self.misses += 1
                return None

            if time.time() - entry['timestamp'] <= self.ttl_seconds:
                entry['last_access'] = time.time()
                self.hits += 1
                return entry['value']

            # Entry expired; remove and count as miss
            del self.cache[key]
            embedding_cache_size.set(len(self.cache))
            self.misses += 1
            return None

    async def set(self, key: str, value: Any):
        """Set value in cache with TTL"""
        with self._lock:
            if len(self.cache) >= self.max_size:
                lru_key = min(
                    self.cache.keys(),
                    key=lambda k: self.cache[k].get('last_access', 0)
                )
                try:
                    logger.debug(f"Embeddings TTLCache evict LRU key={lru_key[:8]}..., size={len(self.cache)}")
                except Exception:
                    pass
                del self.cache[lru_key]

            self.cache[key] = {
                'value': value,
                'timestamp': time.time(),
                'last_access': time.time()
            }
            embedding_cache_size.set(len(self.cache))

    async def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self.cache.clear()
            embedding_cache_size.set(0)
            self.hits = 0
            self.misses = 0

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self.hits + self.misses
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'ttl_seconds': self.ttl_seconds,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': (self.hits / total_requests) if total_requests else 0.0
            }

# ============================================================================
# Enhanced Connection Pool Manager with Cleanup
# ============================================================================

class ConnectionPoolManager:
    """Manages connection pools with proper cleanup"""

    def __init__(self):
        self.pools: Dict[str, aiohttp.ClientSession] = {}
        self.lock = Lock()
        self._closed = False

    async def get_session(self, provider: str) -> aiohttp.ClientSession:
        """Get or create session for provider"""
        async with self.lock:
            if self._closed:
                # Service is spinning back up; allow sessions to be recreated.
                self._closed = False

            existing = self.pools.get(provider)
            if existing is not None and existing.closed:
                # Drop stale session so a fresh one can be created.
                try:
                    await existing.close()
                except Exception:
                    pass
                existing = None
                self.pools.pop(provider, None)

            if provider not in self.pools:
                connector = aiohttp.TCPConnector(
                    limit=CONNECTION_POOL_SIZE,
                    limit_per_host=CONNECTION_POOL_SIZE,
                    force_close=True  # Force close connections on errors
                )
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                self.pools[provider] = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout
                )
            return self.pools[provider]

    async def close_all(self):
        """Close all connection pools"""
        async with self.lock:
            self._closed = True
            for session in self.pools.values():
                await session.close()
            self.pools.clear()

    async def remove_provider(self, provider: str):
        """Remove and close specific provider's session"""
        async with self.lock:
            if provider in self.pools:
                await self.pools[provider].close()
                del self.pools[provider]

# ============================================================================
# Initialize Circuit Breakers for Each Provider
# ============================================================================

def get_or_create_circuit_breaker(provider: str) -> CircuitBreaker:
    """Get or create circuit breaker for provider"""
    breaker_name = f"embeddings_{provider}"
    breaker = circuit_breaker_registry.get(breaker_name)

    if not breaker:
        breaker = CircuitBreaker(
            name=breaker_name,
            failure_threshold=CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            recovery_timeout=CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            expected_exception=(ConnectionError, TimeoutError, aiohttp.ClientError),
            success_threshold=CIRCUIT_BREAKER_SUCCESS_THRESHOLD
        )
        circuit_breaker_registry.register(breaker)

    return breaker

# ============================================================================
# Global Instances
# ============================================================================

embedding_cache = TTLCache()
connection_manager = ConnectionPoolManager()

# Helper to conditionally apply rate limiting
def apply_rate_limit(limit_string: str):
    """No-op by default; enable via env EMBEDDINGS_RATE_LIMIT=on"""
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            if os.getenv("EMBEDDINGS_RATE_LIMIT", "off").lower() == "on":
                limited_func = limiter.limit(limit_string)(f)
                return await limited_func(*args, **kwargs)
            return await f(*args, **kwargs)
        return wrapper
    return decorator

@asynccontextmanager
async def _embeddings_router_lifespan(app):
    # Startup
    logger.info("Starting embeddings service v5 enhanced (with circuit breaker)")
    await embedding_cache.start_cleanup_task()
    if not EMBEDDINGS_AVAILABLE:
        logger.error("Embeddings implementation not available - service will not function")
    try:
        ci = os.getenv("CI", "").lower() == "true"
        auto_dl = os.getenv("AUTO_DOWNLOAD_MODELS", "true").lower() == "true"
        if ci and auto_dl:
            async def _preload_models_on_startup():
                try:
                    cfg = settings.get("EMBEDDING_CONFIG", {}) or {}
                    preload_list = []
                    env_models = os.getenv("PRELOAD_EMBEDDING_MODELS")
                    if env_models:
                        preload_list.extend([m.strip() for m in env_models.split(",") if m.strip()])
                    try:
                        cfg_preload = cfg.get("preload_models", []) or []
                        if isinstance(cfg_preload, list):
                            preload_list.extend([str(m).strip() for m in cfg_preload if str(m).strip()])
                    except Exception:
                        pass
                    default_model = cfg.get("embedding_model") or cfg.get("default_model_id") or "sentence-transformers/all-MiniLM-L6-v2"
                    default_provider = cfg.get("embedding_provider") or "huggingface"
                    if default_model:
                        if ":" in default_model:
                            preload_list.append(default_model)
                        else:
                            preload_list.append(f"{default_provider}:{default_model}")
                    seen = set(); final_models = []
                    for m in preload_list:
                        if m and m not in seen:
                            seen.add(m); final_models.append(m)
                    if final_models:
                        logger.info(f"CI detected; preloading {len(final_models)} embedding model(s): {final_models}")
                        for full in final_models:
                            try:
                                if ":" in full:
                                    prov, mdl = full.split(":", 1)
                                    provider = prov.strip().lower(); model = mdl.strip()
                                else:
                                    model = full.strip(); provider = guess_provider_for_model(model)
                                if not is_model_allowed(provider, model):
                                    logger.warning(f"Skipping preload for disallowed model {provider}:{model}")
                                    continue
                                if provider == "openai" and not settings.get("OPENAI_API_KEY"):
                                    logger.info("Skipping OpenAI preload due to missing OPENAI_API_KEY")
                                    continue
                                await create_embeddings_batch_async(texts=["ci preload"], provider=provider, model_id=model)
                                logger.info(f"Preloaded model {provider}:{model}")
                            except Exception as e:
                                logger.warning(f"Failed to preload model {full}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error during preload task: {e}")
            asyncio.create_task(_preload_models_on_startup())
    except Exception as e:
        logger.error(f"Failed to schedule model preloads: {e}")
    logger.info("Embeddings service started successfully")

    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down embeddings service")
        await embedding_cache.stop_cleanup_task()
        await connection_manager.close_all()
        logger.info("Embeddings service shutdown complete")

router = APIRouter(
    tags=["embeddings"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
        503: {"description": "Service unavailable"}
    },
    lifespan=_embeddings_router_lifespan,
)


# Implemented provider set for 501 guard
IMPLEMENTED_PROVIDERS = {"openai", "huggingface", "onnx", "local_api", "cohere", "google"}


# Register cleanup on process exit
def cleanup_on_exit():
    """Synchronous cleanup for process exit"""
    # Avoid logging in atexit, as sinks may already be closed.
    # Prefer asyncio.run to avoid relying on a possibly-missing current loop in 3.11+.
    try:
        try:
            asyncio.run(embedding_cache.stop_cleanup_task())
        except RuntimeError:
            # If a running loop prevents asyncio.run, fall back to best-effort
            pass
        try:
            asyncio.run(connection_manager.close_all())
        except RuntimeError:
            pass
    except Exception:
        # Swallow any errors during interpreter teardown
        pass

atexit.register(cleanup_on_exit)

# ============================================================================
# Helper Functions
# ============================================================================

@lru_cache(maxsize=128)
def get_tokenizer(model_name: str):
    """Get or create a tokenizer for the model"""
    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        logger.warning(f"No tokenizer for model '{model_name}', using cl100k_base")
        return tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str, model_name: str) -> int:
    """Count tokens in a string"""
    try:
        encoding = get_tokenizer(model_name)
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Token counting failed: {e}, estimating")
        return len(text) // 4

def get_cache_key(text: str, provider: str, model: str, dimensions: Optional[int] = None) -> str:
    """Generate cache key for embedding"""
    key_parts = [text, provider, model]
    if dimensions:
        key_parts.append(str(dimensions))
    key_string = "|".join(key_parts)
    return hashlib.sha256(key_string.encode()).hexdigest()


# ---------------------------------------------------------------------------
# On-demand vector compaction (admin only)
# ---------------------------------------------------------------------------

class CompactorRunRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, description="Target user_id; defaults to current admin in single-user mode")
    media_db_path: Optional[str] = Field(default=None, description="Override path to Media_DB_v2.db; defaults to settings")


class CompactorRunResponse(BaseModel):
    user_id: str
    collections_touched: int
    ts: float


@router.post(
    "/embeddings/compactor/run",
    response_model=CompactorRunResponse,
    summary="Run a one-shot vector compaction for a user (admin only)"
)
async def run_compactor_once(
    req: CompactorRunRequest,
    current_user: User = Depends(get_request_user),
):
    require_admin(current_user)
    try:
        # Lazy import to avoid heavy imports on module import
        from tldw_Server_API.app.core.Embeddings.services.vector_compactor import compact_once as _compact_once  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="Compactor unavailable")
    uid = str(req.user_id or current_user.id)
    try:
        touched = await _compact_once(uid, db_path=req.media_db_path or None)
        return CompactorRunResponse(user_id=uid, collections_touched=int(touched or 0), ts=datetime.utcnow().timestamp())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compactor run failed: {e}")

# ============================================================================
# Token-array handling and dimension adjustment helpers
# ============================================================================

def tokens_to_texts(
    tokens_input: Union[List[int], List[List[int]]],
    model_name: str
) -> Tuple[List[str], int]:
    """Convert token arrays to text using model tokenizer when possible.

    Returns (texts, total_token_count). Uses tiktoken encoding_for_model or cl100k_base fallback.
    """
    try:
        enc = get_tokenizer(model_name)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")

    texts: List[str] = []
    total_tokens = 0
    # Single token array
    if tokens_input and isinstance(tokens_input, list) and tokens_input and isinstance(tokens_input[0], int):
        arr = tokens_input  # type: ignore[assignment]
        total_tokens += len(arr)
        try:
            texts.append(enc.decode(arr))
        except Exception:
            texts.append("")
        return texts, total_tokens

    # Batch of token arrays
    if tokens_input and isinstance(tokens_input, list):
        for arr in tokens_input:  # type: ignore[assignment]
            if not isinstance(arr, list) or not all(isinstance(x, int) for x in arr):
                raise ValueError("Invalid token array format")
            total_tokens += len(arr)
            try:
                texts.append(enc.decode(arr))
            except Exception:
                texts.append("")
        return texts, total_tokens

    raise ValueError("Invalid token array input")

def _dimension_policy() -> str:
    # reduce (slice), pad, or ignore
    try:
        val = os.getenv("EMBEDDINGS_DIMENSION_POLICY", "reduce").lower()
        if val in ("reduce", "pad", "ignore"):
            return val
    except Exception:
        pass
    return "reduce"

def adjust_dimensions(
    vectors: List[List[float]],
    target_dim: Optional[int],
    provider: str,
    model: str
) -> List[List[float]]:
    if not target_dim or target_dim <= 0:
        return vectors
    policy = _dimension_policy()
    adjusted: List[List[float]] = []
    for v in vectors:
        if not isinstance(v, (list, tuple)):
            adjusted.append(v)
            continue
        arr = np.asarray(v, dtype=np.float32)
        cur = arr.shape[0]
        if cur == target_dim or policy == "ignore":
            adjusted.append(arr.tolist())
            continue
        if cur > target_dim:
            # reduce by slicing first-N
            out = arr[:target_dim]
            adjusted.append(out.tolist())
            embedding_dimension_adjustments_total.labels(provider=provider, model=model, method="reduce").inc()
        else:
            if policy == "pad":
                # zero-pad
                pad = np.zeros((target_dim - cur,), dtype=np.float32)
                out = np.concatenate([arr, pad], axis=0)
                adjusted.append(out.tolist())
                embedding_dimension_adjustments_total.labels(provider=provider, model=model, method="pad").inc()
            else:
                # reduce policy cannot expand; return as-is
                adjusted.append(arr.tolist())
    return adjusted

def _should_enforce_policy(user: Optional[User] = None) -> bool:
    # 1) Explicit env override takes highest precedence
    env_val = os.getenv("EMBEDDINGS_ENFORCE_POLICY")
    if env_val is not None:
        return env_val.lower() in ("true", "1", "yes")
    # 2) In TESTING, always enforce (even for admin) for deterministic behavior
    if os.getenv("TESTING", "").lower() in ("true", "1", "yes"):
        return True
    # 3) Settings-level boolean if provided
    try:
        cfg_val = settings.get("EMBEDDINGS_ENFORCE_POLICY", None)
        if isinstance(cfg_val, bool):
            return cfg_val
    except Exception:
        pass
    # 4) Admin bypass unless strict enforcement requested
    try:
        if user and getattr(user, 'is_admin', False) and os.getenv("EMBEDDINGS_ENFORCE_POLICY_STRICT", "false").lower() not in ("true", "1", "yes"):
            return False
    except Exception:
        pass
    # Default: do not enforce
    return False

def resolve_fallback_chain(primary_provider: str) -> List[str]:
    # Configurable chain; else default
    try:
        mapping = settings.get("EMBEDDINGS_FALLBACK_CHAIN", {}) or {}
        if isinstance(mapping, dict):
            chain = mapping.get(primary_provider, None)
            if isinstance(chain, list) and chain:
                return [primary_provider] + [p for p in chain if isinstance(p, str)]
    except Exception:
        pass
    defaults = {
        "openai": ["openai", "huggingface", "onnx", "local_api"],
        "huggingface": ["huggingface", "onnx", "local_api"],
        "onnx": ["onnx", "huggingface", "local_api"],
        "local_api": ["local_api", "huggingface"],
    }
    return defaults.get(primary_provider, [primary_provider])

def _fallback_model_map() -> Dict[str, Dict[str, str]]:
    """Return mapping for provider-specific model fallbacks.

    Shape: {"<src_provider>:<src_model>": {"<dst_provider>": "<dst_model>"}}
    """
    try:
        m = settings.get("EMBEDDINGS_FALLBACK_MODEL_MAP", None)
        if isinstance(m, dict) and m:
            return m
    except Exception:
        pass
    # Sensible defaults for common OpenAI → HF mapping
    return {
        "openai:text-embedding-3-small": {
            "huggingface": "sentence-transformers/all-MiniLM-L6-v2",
            "onnx": "sentence-transformers/all-MiniLM-L6-v2",
            "local_api": "sentence-transformers/all-MiniLM-L6-v2",
        },
        "openai:text-embedding-3-large": {
            "huggingface": "sentence-transformers/all-mpnet-base-v2",
            "onnx": "sentence-transformers/all-mpnet-base-v2",
            "local_api": "sentence-transformers/all-mpnet-base-v2",
        },
        "openai:text-embedding-ada-002": {
            "huggingface": "sentence-transformers/all-mpnet-base-v2",
            "onnx": "sentence-transformers/all-mpnet-base-v2",
            "local_api": "sentence-transformers/all-mpnet-base-v2",
        },
    }

def map_model_for_provider(src_provider: str, dst_provider: str, model_id: str) -> str:
    """Map a model id to the destination provider if a mapping exists."""
    if not src_provider or not dst_provider:
        return model_id
    if src_provider == dst_provider:
        return model_id
    key = f"{src_provider}:{model_id}"
    mapping = _fallback_model_map()
    try:
        dst_map = mapping.get(key, {})
        mapped = dst_map.get(dst_provider)
        if isinstance(mapped, str) and mapped:
            return mapped
    except Exception:
        pass
    return model_id

# Models that require trust_remote_code=True for HuggingFace loading
def _hf_trusts_remote_code(model_name: str) -> bool:
    try:
        patterns = settings.get("TRUSTED_HF_REMOTE_CODE_MODELS", []) or []
        for pat in patterns:
            if fnmatch(model_name, pat) or fnmatch(model_name.lower(), pat.lower()):
                logger.info(f"HF trust_remote_code enabled for model '{model_name}' (matched '{pat}')")
                return True
        return False
    except Exception as e:
        logger.warning(f"Failed to evaluate TRUSTED_HF_REMOTE_CODE_MODELS for '{model_name}': {e}")
        return False

# ============================================================================
# Public Configuration Endpoint
# ============================================================================

@router.get("/embeddings/providers-config", summary="List configured embedding providers and models")
async def get_embeddings_providers_config(current_user: User = Depends(get_request_user)):
    """Return enabled providers and their models from the simplified embeddings config.

    Response:
        {
          "default_provider": str,
          "default_model": str,
          "providers": [ {"name": str, "models": [str, ...]}, ... ]
        }
    """
    try:
        from tldw_Server_API.app.core.Embeddings.simplified_config import get_config as _get_cfg
        cfg = _get_cfg()
        providers = []
        for p in cfg.get_enabled_providers():
            providers.append({
                "name": p.name,
                "models": list(p.models or [])
            })
        return {
            "default_provider": cfg.default_provider,
            "default_model": cfg.default_model,
            "providers": providers,
        }
    except Exception as e:
        logger.error(f"Failed to read embeddings providers config: {e}")
        raise HTTPException(status_code=500, detail="Failed to load embeddings configuration")

# ============================================================================
# Models and Warmup/Download Utilities
# ============================================================================

def is_model_allowed(provider: str, model: str) -> bool:
    providers = _get_allowed_providers()
    models = _get_allowed_models()
    if providers is not None and provider.lower() not in providers:
        return False
    if models is not None:
        for pat in models:
            if pat.endswith("*") and model.startswith(pat[:-1]):
                return True
            if model == pat:
                return True
        return False
    return True

def guess_provider_for_model(model: str, explicit_provider: Optional[str] = None) -> str:
    if explicit_provider:
        return explicit_provider.lower()
    if ":" in model:
        p, _ = model.split(":", 1)
        return p.lower()
    # Heuristic for HF-style ids
    if "/" in model or model.startswith((
        "sentence-transformers/","BAAI/","thenlper/","intfloat/","hkunlp/","Qwen/","microsoft/",
        "google/","facebook/","all-MiniLM-","all-mpnet-","bert-","roberta-","xlm-","distilbert-"
    )):
        if model not in ["text-embedding-3-small","text-embedding-3-large","text-embedding-ada-002"]:
            return "huggingface"
    return "openai"

# ============================================================================
# Provider Configuration Builders
# ============================================================================

def build_provider_config(
    provider: EmbeddingProvider,
    model: str,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    dimensions: Optional[int] = None
) -> Dict[str, Any]:
    """Build provider-specific configuration"""

    if provider == EmbeddingProvider.OPENAI:
        return {
            "provider": "openai",
            "model_name_or_path": model,
            "api_key": api_key or settings.get("OPENAI_API_KEY"),
        }
    elif provider == EmbeddingProvider.HUGGINGFACE:
        return {
            "provider": "huggingface",
            "model_name_or_path": model,
            "trust_remote_code": _hf_trusts_remote_code(model),
            "hf_cache_dir_subpath": "huggingface_cache",
        }
    elif provider == EmbeddingProvider.COHERE:
        return {
            "provider": "cohere",
            "model_name_or_path": model,
            "api_key": api_key or settings.get("COHERE_API_KEY"),
        }
    elif provider == EmbeddingProvider.VOYAGE:
        return {
            "provider": "voyage",
            "model_name_or_path": model,
            "api_key": api_key or settings.get("VOYAGE_API_KEY"),
        }
    elif provider == EmbeddingProvider.GOOGLE:
        return {
            "provider": "google",
            "model_name_or_path": model,
            "api_key": api_key or settings.get("GOOGLE_API_KEY"),
        }
    elif provider == EmbeddingProvider.MISTRAL:
        return {
            "provider": "mistral",
            "model_name_or_path": model,
            "api_key": api_key or settings.get("MISTRAL_API_KEY"),
        }
    elif provider == EmbeddingProvider.ONNX:
        return {
            "provider": "onnx",
            "model_name_or_path": model,
        }
    elif provider == EmbeddingProvider.LOCAL_API:
        return {
            "provider": "local_api",
            "model_name_or_path": model,
            "api_url": api_url or settings.get("LOCAL_API_URL"),
        }
    else:
        raise ValueError(f"Unknown provider: {provider}")

# ============================================================================
# Enhanced Embedding Function with Circuit Breaker
# ============================================================================

async def create_embeddings_with_circuit_breaker(
    texts: List[str],
    provider: str,
    model_id: str,
    config: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> List[List[float]]:
    """Create embeddings with circuit breaker protection"""
    breaker = get_or_create_circuit_breaker(provider)

    try:
        # Use circuit breaker to protect the call
        async def _create():
            # Build proper typed ModelCfg based on provider
            if provider == "huggingface":
                model_cfg = HFModelCfg(
                    provider="huggingface",
                    model_name_or_path=config.get("model_name_or_path", model_id),
                    trust_remote_code=config.get("trust_remote_code", False),
                    hf_cache_dir_subpath=config.get("hf_cache_dir_subpath", "huggingface_cache"),
                )
            elif provider == "openai":
                model_cfg = OpenAIModelCfg(
                    provider="openai",
                    model_name_or_path=config.get("model_name_or_path", model_id),
                )
            elif provider == "onnx":
                model_cfg = ONNXModelCfg(
                    provider="onnx",
                    model_name_or_path=config.get("model_name_or_path", model_id),
                    onnx_storage_dir_subpath=config.get("onnx_storage_dir_subpath", "onnx_models"),
                )
            elif provider == "local_api":
                model_cfg = LocalAPICfg(
                    provider="local_api",
                    model_name_or_path=config.get("model_name_or_path", model_id),
                    api_url=config.get("api_url"),
                    api_key=config.get("api_key"),
                )
            elif provider == "cohere":
                # Direct async call to Cohere embeddings
                api_key = config.get("api_key") or settings.get("COHERE_API_KEY")
                if not api_key:
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cohere API key not configured")
                mdl = config.get("model_name_or_path", model_id) or "embed-english-v3.0"
                session = await connection_manager.get_session(provider)
                url = "https://api.cohere.com/v1/embed"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"model": mdl, "texts": texts, "input_type": "search_document"}
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status >= 400:
                        detail = await resp.text()
                        raise HTTPException(status_code=resp.status, detail=f"Cohere error: {detail}")
                    data = await resp.json()
                    embs = None
                    try:
                        if isinstance(data.get("embeddings"), list):
                            embs = data["embeddings"]
                        elif isinstance(data.get("embeddings"), dict) and "float" in data["embeddings"]:
                            embs = data["embeddings"]["float"]
                    except Exception:
                        embs = None
                    if not embs:
                        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid Cohere response format")
                    return embs
            elif provider == "google":
                # Direct async call to Google Generative Language API (text-embedding-004)
                api_key = config.get("api_key") or settings.get("GOOGLE_API_KEY")
                if not api_key:
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google API key not configured")
                raw_model = config.get("model_name_or_path", model_id) or "models/text-embedding-004"
                model_name = raw_model if raw_model.startswith("models/") else f"models/{raw_model}"
                session = await connection_manager.get_session(provider)
                base = "https://generativelanguage.googleapis.com/v1beta"
                url = f"{base}/{model_name}:batchEmbedContents?key={api_key}"
                reqs = [{"model": model_name, "content": {"parts": [{"text": t}]}} for t in texts]
                payload = {"requests": reqs}
                async with session.post(url, json=payload) as resp:
                    if resp.status >= 400:
                        detail = await resp.text()
                        raise HTTPException(status_code=resp.status, detail=f"Google Embeddings error: {detail}")
                    data = await resp.json()
                    embs = []
                    try:
                        items = data.get("embeddings") or []
                        for it in items:
                            vec = it.get("values") or it.get("embedding") or []
                            if isinstance(vec, dict) and "values" in vec:
                                vec = vec["values"]
                            if not isinstance(vec, list):
                                raise ValueError("invalid embedding vector")
                            embs.append(vec)
                    except Exception:
                        embs = []
                    if not embs or len(embs) != len(texts):
                        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid Google embeddings response format")
                    return embs
            else:
                raise ValueError(f"Unknown provider: {provider}")

            # Wrap config in expected structure for embeddings service batch helper
            # Include explicit defaults so batching helper does not fall back to OpenAI
            provider_qualified_id = f"{provider}:{model_id}"
            app_config = {
                "embedding_config": {
                    "default_model_id": provider_qualified_id,
                    "default_provider": provider,
                    "default_model": model_id,
                    "model_storage_base_dir": resolve_model_storage_base_dir(),
                    "models": {provider_qualified_id: model_cfg},
                }
            }

            # Pass provider-qualified override to avoid implicit defaults inside the batcher
            return await batching_create_embeddings_batch_async(
                texts=texts,
                config=app_config,
                model_id_override=provider_qualified_id,
                metadata=metadata,
            )

        return await breaker.call_async(_create)

    except CircuitBreakerError as e:
        logger.warning(f"Circuit breaker open for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service temporarily unavailable for provider {provider}. Please try again later."
        )
    except Exception as e:
        logger.error(f"Failed to create embeddings with {provider}: {e}")
        raise

async def create_embeddings_batch_async(
    texts: List[str],
    provider: str,
    model_id: Optional[str] = None,
    dimensions: Optional[int] = None,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[List[float]]:
    """Async wrapper for embeddings with caching and circuit breaker"""

    embeddings = []
    uncached_texts = []
    uncached_indices = []

    # Check cache
    for i, text in enumerate(texts):
        cache_key = get_cache_key(text, provider, model_id or "default", dimensions)
        cached = await embedding_cache.get(cache_key)

        if cached:
            embeddings.append(cached)
            # Ensure Prometheus labels are always strings
            embedding_cache_hits.labels(provider=provider, model=(model_id or "default")).inc()
        else:
            embeddings.append(None)
            uncached_texts.append(text)
            uncached_indices.append(i)

    # Process uncached texts
    if uncached_texts:
        try:
            provider_enum = EmbeddingProvider(provider)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown provider: {provider}"
            )

        config = build_provider_config(
            provider_enum,
            model_id,
            api_key,
            api_url,
            dimensions
        )

        # Process in batches with circuit breaker (or synthesize in test mode for OpenAI)
        all_new_embeddings = []
        if provider == "openai" and os.getenv("TESTING", "").lower() == "true" and os.getenv("USE_REAL_OPENAI_IN_TESTS", "").lower() != "true":
            import numpy as _np
            mdl = (model_id or "text-embedding-3-small").lower()
            dim = 1536
            if "3-large" in mdl:
                dim = 3072
            for t in uncached_texts:
                seed = int(hashlib.sha256(((model_id or "") + "|" + t).encode("utf-8")).hexdigest()[:16], 16)
                rng = _np.random.default_rng(seed)
                vec = rng.standard_normal(dim, dtype=_np.float32)
                nrm = _np.linalg.norm(vec)
                if nrm > 0:
                    vec = vec / nrm
                all_new_embeddings.append(vec.tolist())
        else:
            for batch_start in range(0, len(uncached_texts), MAX_BATCH_SIZE):
                batch_end = min(batch_start + MAX_BATCH_SIZE, len(uncached_texts))
                batch_texts = uncached_texts[batch_start:batch_end]

                try:
                    batch_embeddings = await create_embeddings_with_circuit_breaker(
                        batch_texts,
                        provider,
                        model_id,
                        config,
                        metadata=metadata,
                    )
                    all_new_embeddings.extend(batch_embeddings)
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Failed to create embeddings for batch: {e}")

                    # Try to close and recreate connection for this provider
                    await connection_manager.remove_provider(provider)

                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Embedding service error: {str(e)}"
                    )

        # Update results and cache
        for i, (idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
            embedding = all_new_embeddings[i]
            embeddings[idx] = embedding

            cache_key = get_cache_key(text, provider, model_id or "default", dimensions)
            await embedding_cache.set(cache_key, embedding)

    return embeddings

# ============================================================================
# Authorization Helpers
# ============================================================================

def require_admin(user: User) -> None:
    """Require admin privileges for endpoint"""
    # In single-user mode, the sole user is considered admin for admin-only ops
    try:
        if is_single_user_mode():
            return
    except Exception:
        pass
    if not user or not getattr(user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/embeddings",
    response_model=CreateEmbeddingResponse,
    status_code=status.HTTP_200_OK,
    summary="Create embeddings (enhanced with circuit breaker)",
    dependencies=[Depends(rbac_rate_limit("embeddings.create"))]
)
@apply_rate_limit("5/second")
async def create_embedding_endpoint(
    request: Request,
    embedding_request: CreateEmbeddingRequest = Body(...),
    current_user: User = Depends(get_request_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    x_provider: Optional[str] = Header(None, alias="x-provider"),
    response: Response = None
):
    """Create embeddings with circuit breaker protection and enhanced error recovery"""

    if not EMBEDDINGS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embeddings service unavailable; dependencies not installed"
        )

    active_embedding_requests.inc()
    start_time = time.time()

    user_metadata = _build_user_metadata(current_user)

    try:
        # Backpressure and tenant quotas
        exc = await _check_backpressure_and_quotas(request, current_user)
        if exc is not None:
            raise exc
        # Validate provider (defer policy checks until after input validation)
        provider = x_provider or "openai"
        model = embedding_request.model

        # Auto-detect provider based on model name if not specified
        if ":" in model:
            parts = model.split(":", 1)
            provider = parts[0]
            model = parts[1]
        elif not x_provider:  # Only auto-detect if provider not explicitly set
            # Common HuggingFace model prefixes/patterns
            huggingface_patterns = [
                "sentence-transformers/",
                "BAAI/",
                "thenlper/",
                "intfloat/",
                "hkunlp/",
                "Qwen/",
                "microsoft/",
                "google/",
                "facebook/",
                "bert-",
                "roberta-",
                "xlm-",
                "distilbert-",
                "all-MiniLM-",
                "all-mpnet-",
            ]

            for pattern in huggingface_patterns:
                if model.startswith(pattern) or "/" in model:
                    openai_models = ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]
                    if model not in openai_models:
                        provider = "huggingface"
                        break

        try:
            provider_enum = EmbeddingProvider(provider.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown provider: {provider}"
            )

        # Parse and validate input FIRST (before policy checks)
        texts_to_embed: List[str] = []
        provided_token_arrays = False
        provided_token_count = 0

        if isinstance(embedding_request.input, str):
            if not embedding_request.input.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Input cannot be empty")
            texts_to_embed = [embedding_request.input]
        elif isinstance(embedding_request.input, list):
            if not embedding_request.input:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Input list cannot be empty")
            if len(embedding_request.input) > 2048:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 2048 inputs allowed")

            # Support list[str], list[int], or list[list[int]]
            if all(isinstance(item, str) for item in embedding_request.input):
                texts_to_embed = embedding_request.input  # type: ignore[assignment]
            elif all(isinstance(item, int) for item in embedding_request.input):
                # Single token array
                try:
                    texts_to_embed, provided_token_count = tokens_to_texts(embedding_request.input, model)
                    provided_token_arrays = True
                    embedding_token_inputs_total.labels(mode="single").inc()
                except Exception:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token array input")
            elif all(isinstance(item, list) for item in embedding_request.input):
                # Batch of token arrays
                try:
                    texts_to_embed, provided_token_count = tokens_to_texts(embedding_request.input, model)
                    provided_token_arrays = True
                    embedding_token_inputs_total.labels(mode="batch").inc()
                except Exception:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token array input")
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input type")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input type")

        # Enforce per-model token length limits (fail-fast)
        max_tokens = _get_model_max_tokens(provider, model)
        too_long: List[Tuple[int, int]] = []  # (index, token_count)
        for idx, t in enumerate(texts_to_embed):
            tok = count_tokens(t, model)
            if tok > max_tokens:
                too_long.append((idx, tok))
        if too_long:
            # Return top-level JSON error object to match tests (not nested under "detail")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "input_too_long",
                    "message": f"One or more inputs exceed max tokens {max_tokens} for model {model}",
                    "details": [{"index": i, "tokens": tok} for (i, tok) in too_long]
                }
            )

        # Provider/model allowlist enforcement (after input validation)
        import os as _os
        # Enforce allowlists based on config/env; admin may bypass unless STRICT is set
        enforce_policy = _should_enforce_policy(current_user)
        allowed_providers = _get_allowed_providers()
        if enforce_policy and allowed_providers is not None and provider.lower() not in allowed_providers:
            embedding_policy_denied_total.labels(provider=provider, model=model, policy_type="provider").inc()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Provider '{provider}' is not allowed")

        allowed_models = _get_allowed_models()
        if enforce_policy and allowed_models is not None:
            def _model_allowed(m: str) -> bool:
                for pat in allowed_models:
                    if pat.endswith("*") and m.startswith(pat[:-1]):
                        return True
                    if m == pat:
                        return True
                return False
            if not _model_allowed(model):
                embedding_policy_denied_total.labels(provider=provider, model=model, policy_type="model").inc()
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Model '{model}' is not allowed")

        # Guard: return 501 for unsupported/unstyled providers (prevents silent fallback)
        try:
            prov_enum = EmbeddingProvider(provider)
        except Exception:
            # Unknown provider is handled as 400 elsewhere, keep behavior consistent
            pass
        else:
            if provider.lower() not in IMPLEMENTED_PROVIDERS:
                raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"Provider '{provider}' not implemented")

        # Create embeddings
        # Special-case for OpenAI in test mode: synthesize vectors deterministically
        use_synthetic_openai = (
            provider == "openai"
            and os.getenv("TESTING", "").lower() == "true"
            and os.getenv("USE_REAL_OPENAI_IN_TESTS", "").lower() != "true"
        )

        embeddings: List[List[float]] = []

        original_provider = provider
        original_model = model

        if use_synthetic_openai:
            dim = 1536
            mid = (model or "").lower()
            if "3-large" in mid:
                dim = 3072
            import numpy as _np
            embeddings = []
            for t in texts_to_embed:
                seed = int(hashlib.sha256((model + "|" + t).encode("utf-8")).hexdigest()[:16], 16)
                rng = _np.random.default_rng(seed)
                vec = rng.standard_normal(dim, dtype=_np.float32)
                nrm = _np.linalg.norm(vec)
                if nrm > 0:
                    vec = vec / nrm
                embeddings.append(vec.tolist())
        else:
            # Try provider with fallback chain on failure
            last_error: Optional[Exception] = None
            # Fallback policy when explicit provider header is present:
            # Strict by default: do NOT fallback when `x-provider` header is set.
            # To allow fallback even with header, set EMBEDDINGS_ALLOW_FALLBACK_WITH_HEADER=true
            try:
                allow_hdr = os.getenv("EMBEDDINGS_ALLOW_FALLBACK_WITH_HEADER", "").lower() in ("1", "true", "yes", "on")
            except Exception:
                allow_hdr = False
            fallback_disabled = (x_provider is not None and not allow_hdr)
            chain = [provider] if fallback_disabled else resolve_fallback_chain(provider)
            if enforce_policy and allowed_providers is not None:
                chain = [p for p in chain if p.lower() in allowed_providers or p == provider]
            fallback_from: Optional[str] = None
            for p in chain:
                try:
                    if p != provider:
                        embedding_fallbacks_total.labels(from_provider=provider, to_provider=p).inc()
                        fallback_from = provider
                    # Map model id to destination provider if needed
                    target_model_id = map_model_for_provider(original_provider, p, original_model)
                    embeddings = await create_embeddings_batch_async(
                        texts=texts_to_embed,
                        provider=p,
                        model_id=target_model_id,
                        dimensions=embedding_request.dimensions,
                        metadata=user_metadata,
                    )
                    provider = p
                    if target_model_id:
                        model = target_model_id
                    # Add response headers to indicate fallback
                    try:
                        if response is not None:
                            response.headers['X-Embeddings-Provider'] = provider
                            if fallback_from and fallback_from != provider:
                                response.headers['X-Embeddings-Fallback-From'] = fallback_from
                    except Exception:
                        pass
                    break
                except HTTPException as he:
                    if he.status_code and 400 <= he.status_code < 500 and he.status_code != 429:
                        embedding_provider_failures.labels(provider=p, model=model, reason=f"http_{he.status_code}").inc()
                        last_error = he
                        break
                    embedding_provider_failures.labels(provider=p, model=model, reason=f"http_{he.status_code or 'unknown'}").inc()
                    last_error = he
                    continue
                except Exception as e:
                    embedding_provider_failures.labels(provider=p, model=model, reason="exception").inc()
                    last_error = e
                    continue
            if not embeddings:
                logger.error(f"Embedding creation failed across providers {chain}: {last_error}")
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Embedding providers unavailable")

        # Optional dimension adjustment (post-process)
        dims_policy_used = None
        if embedding_request.dimensions:
            # For base64 outputs, always reduce to requested dims for deterministic length
            if embedding_request.encoding_format == "base64":
                try:
                    import numpy as _np
                    target = int(embedding_request.dimensions)
                    adjusted: List[List[float]] = []
                    for v in embeddings:
                        try:
                            arr = _np.asarray(v, dtype=_np.float32)
                            if arr.shape[0] > target:
                                arr = arr[:target]
                            adjusted.append(arr.tolist())
                        except Exception:
                            adjusted.append(v)
                    embeddings = adjusted
                    dims_policy_used = "reduce"
                except Exception:
                    # Fallback to normal policy if anything goes wrong
                    dims_policy_used = _dimension_policy()
                    embeddings = adjust_dimensions(embeddings, embedding_request.dimensions, provider, model)
            else:
                dims_policy_used = _dimension_policy()
                embeddings = adjust_dimensions(embeddings, embedding_request.dimensions, provider, model)
            # Add response header for visibility
            try:
                if response is not None and dims_policy_used:
                    response.headers['X-Embeddings-Dimensions-Policy'] = dims_policy_used
            except Exception:
                pass

        # Format response
        output_data = []
        for i, embedding in enumerate(embeddings):
            # Ensure vectors are L2-normalized for numeric output
            arr = np.array(embedding, dtype=np.float32)
            norm = np.linalg.norm(arr)
            if norm > 0 and embedding_request.encoding_format != "base64":
                arr = arr / norm
            if embedding_request.encoding_format == "base64":
                processed_value = base64.b64encode(arr.tobytes()).decode('utf-8')
            else:
                processed_value = arr.tolist()

            output_data.append(
                EmbeddingData(
                    embedding=processed_value,
                    index=i
                )
            )

        # Calculate token usage
        if provided_token_arrays:
            num_tokens = provided_token_count
        else:
            num_tokens = sum(count_tokens(text, model) for text in texts_to_embed)

        # Track metrics
        duration = time.time() - start_time
        embedding_request_duration.labels(
            provider=provider,
            model=model
        ).observe(duration)

        embedding_requests_total.labels(
            provider=provider,
            model=model,
            status="success"
        ).inc()

        logger.info(
            f"Created {len(output_data)} embeddings",
            extra={
                "user_id": current_user.id,
                "provider": provider,
                "model": model,
                "duration": duration,
                "fallback_from": original_provider if original_provider != provider else None,
                "dimensions_policy": dims_policy_used,
            }
        )

        # Persist a usage log entry (best-effort)
        try:
            user_id = getattr(current_user, 'id', None)
            api_key_id = None
            try:
                if request is not None and hasattr(request, 'state'):
                    api_key_id = getattr(request.state, 'api_key_id', None)
            except Exception:
                api_key_id = None
            await log_llm_usage(
                user_id=user_id,
                key_id=api_key_id,
                endpoint=f"{request.method}:{request.url.path}",
                operation="embeddings",
                provider=provider,
                model=model,
                status=200,
                latency_ms=int((duration) * 1000),
                prompt_tokens=int(num_tokens or 0),
                completion_tokens=0,
                total_tokens=int(num_tokens or 0),
                request_id=request.headers.get('X-Request-ID') if request else None,
            )
        except Exception:
            pass

        # Attach quota headers if set
        try:
            if hasattr(request, 'state') and response is not None:
                if getattr(request.state, 'rate_limit_limit', None) is not None:
                    response.headers["X-RateLimit-Limit"] = str(getattr(request.state, 'rate_limit_limit'))
                    response.headers["X-RateLimit-Remaining"] = str(getattr(request.state, 'rate_limit_remaining'))
        except Exception:
            pass

        return CreateEmbeddingResponse(
            data=output_data,
            model=f"{provider}:{model}" if provider != "openai" else model,
            usage=EmbeddingUsage(
                prompt_tokens=num_tokens,
                total_tokens=num_tokens
            )
        )

    finally:
        active_embedding_requests.dec()

class EmbeddingsBatchRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1, description="Texts to embed")
    model: Optional[str] = Field(None, description="Embedding model identifier")
    provider: Optional[str] = Field(None, description="Embedding provider override")
    dimensions: Optional[int] = Field(None, description="Requested output dimensions if supported")
    batch_size: Optional[int] = Field(None, description="Hint for provider batch sizing")


class EmbeddingsBatchResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    provider: str
    count: int


@router.post(
    "/embeddings/batch",
    response_model=EmbeddingsBatchResponse,
    summary="Create embeddings for a batch of texts"
)
async def create_embeddings_batch_endpoint(
    payload: EmbeddingsBatchRequest,
    current_user: User = Depends(get_request_user),
    request: Request = None,
    response: Response = None
) -> EmbeddingsBatchResponse:
    texts = payload.texts or []
    if not texts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="texts must not be empty")

    for text in texts:
        if not isinstance(text, str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All texts must be strings")
        if not text.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="texts cannot contain empty strings")

    model, provider = _resolve_model_and_provider(payload.model, payload.provider)

    enforce_policy = _should_enforce_policy(current_user)
    allowed_providers = _get_allowed_providers()
    if enforce_policy and allowed_providers is not None and provider.lower() not in allowed_providers:
        embedding_policy_denied_total.labels(provider=provider, model=model, policy_type="provider").inc()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Provider '{provider}' is not allowed")

    if enforce_policy and not is_model_allowed(provider, model):
        embedding_policy_denied_total.labels(provider=provider, model=model, policy_type="model").inc()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Model '{model}' is not allowed")

    max_tokens = _get_model_max_tokens(provider, model)
    too_long = []
    for idx, text in enumerate(texts):
        tok = count_tokens(text, model)
        if tok > max_tokens:
            too_long.append({"index": idx, "tokens": tok})

    if too_long:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "input_too_long",
                "message": f"One or more inputs exceed max tokens {max_tokens} for model {model}",
                "details": too_long
            }
        )

    # Backpressure and tenant quotas (best-effort; request may be None in some test paths)
    try:
        if request is not None:
            exc = await _check_backpressure_and_quotas(request, current_user)
            if exc is not None:
                raise exc
    except HTTPException:
        raise
    except Exception:
        pass

    user_metadata = _build_user_metadata(current_user)

    embeddings = await create_embeddings_batch_async(
        texts=texts,
        provider=provider,
        model_id=model,
        dimensions=payload.dimensions,
        metadata=user_metadata,
    )

    # Attach quota headers if present (parity with single-item endpoint)
    try:
        if hasattr(request, 'state') and response is not None:
            if getattr(request.state, 'rate_limit_limit', None) is not None:
                response.headers["X-RateLimit-Limit"] = str(getattr(request.state, 'rate_limit_limit'))
                response.headers["X-RateLimit-Remaining"] = str(getattr(request.state, 'rate_limit_remaining'))
    except Exception:
        pass

    return EmbeddingsBatchResponse(
        embeddings=embeddings,
        model=model,
        provider=provider,
        count=len(embeddings)
    )


# ============================================================================
# Model Management Endpoints
# ============================================================================

@router.get("/embeddings/models", summary="List available embedding models")
async def list_embedding_models():
    """List configured/known models with allowlist status."""
    cfg = settings.get("EMBEDDING_CONFIG", {}) or {}
    default_model = cfg.get("default_model_id") or cfg.get("embedding_model") or "text-embedding-3-small"
    default_provider = cfg.get("embedding_provider", "openai")

    # Collect known models from provider table + default
    known: List[Dict[str, Any]] = []
    seen = set()
    # static provider models
    for prov, lst in PROVIDER_MODELS.items():
        for m in lst:
            key = (prov.value, m)
            if key in seen:
                continue
            seen.add(key)
            allowed = is_model_allowed(prov.value, m)
            known.append({"provider": prov.value, "model": m, "allowed": allowed, "default": False})
    # add default
    default_marked = False
    for item in known:
        if item.get("provider") == default_provider and item.get("model") == default_model:
            item["default"] = True
            default_marked = True
            break
    if not default_marked:
        known.append({
            "provider": default_provider,
            "model": default_model,
            "allowed": is_model_allowed(default_provider, default_model),
            "default": True
        })

    return {"data": known, "allowed_providers": _get_allowed_providers(), "allowed_models": _get_allowed_models()}


@router.get("/embeddings/models/{model_id:path}", summary="Get embedding model metadata")
async def get_embedding_model_info(
    model_id: str,
    provider: Optional[str] = Query(None, description="Provider override"),
    current_user: User = Depends(get_request_user)
):
    model = model_id
    resolved_provider = guess_provider_for_model(model, provider)

    if not is_model_allowed(resolved_provider, model):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not available")

    user_metadata = _build_user_metadata(current_user)

    try:
        vectors = await create_embeddings_batch_async(
            texts=["model probe"],
            provider=resolved_provider,
            model_id=model,
            metadata=user_metadata,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Model info probe failed for {resolved_provider}:{model}: {exc}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Embedding service unavailable")

    dimension = None
    if vectors and vectors[0]:
        first = vectors[0]
        if isinstance(first, (list, tuple, np.ndarray)):
            dimension = len(first)

    max_tokens = _get_model_max_tokens(resolved_provider, model)

    return {
        "model": model,
        "provider": resolved_provider,
        "dimension": dimension,
        "max_tokens": max_tokens,
        "allowed": True
    }


class TenantQuotaResponse(BaseModel):
    limit_rps: int
    remaining: Optional[int] = None


@router.get("/embeddings/tenant/quotas", summary="Get current tenant quotas (if multi-tenant)")
async def get_tenant_quotas(current_user: User = Depends(get_request_user)) -> TenantQuotaResponse:
    if is_single_user_mode() or TENANT_RPS <= 0:
        return TenantQuotaResponse(limit_rps=0, remaining=None)
    try:
        client = await _get_redis_client()
        ts = int(time.time())
        key = f"embeddings:tenant:rps:{getattr(current_user, 'id', 'anon')}:{ts}"
        val = await client.get(key)
        await ensure_async_client_closed(client)
        used = int(val or 0)
        return TenantQuotaResponse(limit_rps=TENANT_RPS, remaining=max(0, TENANT_RPS - used))
    except Exception:
        return TenantQuotaResponse(limit_rps=TENANT_RPS, remaining=None)


class PriorityBumpRequest(BaseModel):
    job_id: str
    priority: str = Field(..., description="one of: high|normal|low")
    ttl_seconds: Optional[int] = Field(default=600, ge=1, le=86400)


@router.post("/embeddings/job/priority/bump", summary="Override/bump job priority for routing into priority queues (best-effort)")
async def bump_job_priority(req: PriorityBumpRequest, current_user: User = Depends(get_request_user)) -> Dict[str, Any]:
    if not getattr(current_user, 'is_admin', False) and not is_single_user_mode():
        raise HTTPException(status_code=403, detail="Admin privileges required")
    pr = (req.priority or "").strip().lower()
    if pr not in ("high", "normal", "low"):
        raise HTTPException(status_code=400, detail="priority must be one of: high|normal|low")
    try:
        client = await _get_redis_client()
        key = f"embeddings:priority:override:{req.job_id}"
        await client.set(key, pr)
        await client.expire(key, int(req.ttl_seconds or 600))
        await ensure_async_client_closed(client)
        return {"status": "ok", "job_id": req.job_id, "priority": pr, "ttl_seconds": int(req.ttl_seconds or 600)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set priority override: {e}")


class ModelActionRequest(BaseModel):
    model: str
    provider: Optional[str] = None


class CollectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Collection name")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Collection metadata")
    embedding_model: Optional[str] = Field(default=None, description="Embedding model to associate")
    provider: Optional[str] = Field(default=None, description="Provider override for dimension detection")


class CollectionResponse(BaseModel):
    name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CollectionStatsResponse(BaseModel):
    name: str
    count: int
    embedding_dimension: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("/embeddings/models/warmup", summary="Warmup (preload) an embedding model (admin)")
async def warmup_model(
    payload: ModelActionRequest,
    current_user: User = Depends(get_request_user)
):
    require_admin(current_user)
    provider = guess_provider_for_model(payload.model, payload.provider)
    if not is_model_allowed(provider, payload.model):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Model/provider not allowed")
    user_metadata = _build_user_metadata(current_user)

    try:
        await create_embeddings_batch_async(
            texts=["model warmup test"],
            provider=provider,
            model_id=payload.model,
            metadata=user_metadata,
        )
        return {"status": "ok", "provider": provider, "model": payload.model, "warmed": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Warmup failed for {provider}:{payload.model}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Warmup failed: {e}")


@router.post("/embeddings/models/download", summary="Download/prepare a model (admin)")
async def download_model(
    payload: ModelActionRequest,
    current_user: User = Depends(get_request_user)
):
    require_admin(current_user)
    provider = guess_provider_for_model(payload.model, payload.provider)
    if not is_model_allowed(provider, payload.model):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Model/provider not allowed")
    user_metadata = _build_user_metadata(current_user)

    try:
        # Trigger a load without depending on real content by generating a small embedding
        await create_embeddings_batch_async(
            texts=["download model"],
            provider=provider,
            model_id=payload.model,
            metadata=user_metadata,
        )
        return {"status": "ok", "provider": provider, "model": payload.model, "downloaded": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed for {provider}:{payload.model}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Download failed: {e}")

@router.delete(
    "/embeddings/cache",
    summary="Clear embedding cache (admin only)"
)
async def clear_cache(
    current_user: User = Depends(get_request_user)
):
    """Clear the embedding cache - requires admin privileges"""

    require_admin(current_user)

    cache_stats = embedding_cache.stats()
    await embedding_cache.clear()

    logger.info(
        f"Cache cleared by admin",
        extra={
            "admin_id": current_user.id,
            "entries_cleared": cache_stats['size']
        }
    )

    return {
        "message": "Cache cleared successfully",
        "entries_removed": cache_stats['size']
    }


# ============================================================================
# Chroma Collection Management
# ============================================================================

@router.post(
    "/embeddings/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a ChromaDB collection"
)
async def create_collection(
    payload: CollectionCreateRequest,
    current_user: User = Depends(get_request_user)
) -> CollectionResponse:
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Collection name is required")

    manager = _chroma_manager_for_user(current_user)

    user_metadata = _build_user_metadata(current_user)

    try:
        manager.client.get_collection(name=name)
    except Exception:
        pass
    else:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Collection '{name}' already exists")

    metadata = payload.metadata.copy() if isinstance(payload.metadata, dict) else {}
    model, provider = _resolve_model_and_provider(payload.embedding_model, payload.provider)

    if payload.embedding_model:
        metadata.setdefault("embedding_model", model)
    metadata.setdefault("provider", provider)

    dimension = None
    try:
        vectors = await create_embeddings_batch_async(
            texts=["collection probe"],
            provider=provider,
            model_id=model,
            metadata=user_metadata,
        )
        if vectors and vectors[0]:
            first = vectors[0]
            if isinstance(first, (list, tuple, np.ndarray)):
                dimension = len(first)
    except Exception as exc:
        logger.warning(f"Collection dimension probe failed for {name}: {exc}")

    if dimension:
        metadata.setdefault("embedding_dimension", dimension)

    collection = manager.client.create_collection(name=name, metadata=metadata)
    coll_metadata = getattr(collection, "metadata", None) or metadata
    return CollectionResponse(name=collection.name, metadata=coll_metadata)


@router.get(
    "/embeddings/collections",
    response_model=List[CollectionResponse],
    summary="List ChromaDB collections"
)
async def list_collections(current_user: User = Depends(get_request_user)) -> List[CollectionResponse]:
    manager = _chroma_manager_for_user(current_user)
    collections = manager.client.list_collections()
    response: List[CollectionResponse] = []
    for collection in collections:
        metadata = getattr(collection, "metadata", {}) or {}
        response.append(CollectionResponse(name=collection.name, metadata=metadata))
    return response


@router.delete(
    "/embeddings/collections/{collection_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a ChromaDB collection"
)
async def delete_collection(
    collection_name: str,
    current_user: User = Depends(get_request_user)
) -> Response:
    manager = _chroma_manager_for_user(current_user)
    try:
        manager.client.delete_collection(name=collection_name)
    except Exception as exc:
        logger.warning(f"Failed to delete collection {collection_name}: {exc}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/embeddings/collections/{collection_name}/stats",
    response_model=CollectionStatsResponse,
    summary="Retrieve collection statistics"
)
async def get_collection_stats(
    collection_name: str,
    current_user: User = Depends(get_request_user)
) -> CollectionStatsResponse:
    manager = _chroma_manager_for_user(current_user)
    try:
        collection = manager.client.get_collection(name=collection_name)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    try:
        count = int(collection.count())
    except Exception:
        try:
            data = collection.get(limit=0, include=[])
            count = len(data.get("ids") or [])
        except Exception:
            count = 0

    metadata = getattr(collection, "metadata", {}) or {}
    dimension = metadata.get("embedding_dimension")

    if dimension is None:
        try:
            sample = collection.get(limit=1, include=["embeddings"])
            embeddings = sample.get("embeddings") or []
            candidate = None
            if embeddings:
                bucket = embeddings[0]
                if isinstance(bucket, list) and bucket:
                    candidate = bucket[0]
                elif isinstance(bucket, (np.ndarray, tuple)):
                    candidate = bucket
            if candidate is not None and hasattr(candidate, "__len__"):
                dimension = len(candidate)
        except Exception:
            pass

    return CollectionStatsResponse(
        name=collection.name,
        count=count,
        embedding_dimension=dimension,
        metadata=metadata
    )

@router.get(
    "/embeddings/health",
    summary="Health check with circuit breaker status"
)
async def health_check():
    """Enhanced health check with circuit breaker status"""

    # Get circuit breaker status for all providers
    breaker_status = {}
    for provider in EmbeddingProvider:
        breaker_name = f"embeddings_{provider.value}"
        breaker = circuit_breaker_registry.get(breaker_name)
        if breaker:
            status_info = breaker.get_status()
            breaker_status[provider.value] = {
                "state": status_info["state"],
                "failure_count": status_info["failure_count"],
                "last_failure": status_info["last_failure_time"]
            }

    try:
        hyde_enabled = bool(settings.get("HYDE_ENABLED", False))
    except Exception:
        hyde_enabled = False
    try:
        hyde_questions = int(settings.get("HYDE_QUESTIONS_PER_CHUNK", 0) or 0)
    except Exception:
        hyde_questions = 0
    hyde_info = {
        "enabled": hyde_enabled,
        "questions_per_chunk": hyde_questions,
    }
    hyde_provider = settings.get("HYDE_PROVIDER")
    hyde_model = settings.get("HYDE_MODEL")
    if hyde_provider:
        hyde_info["provider"] = hyde_provider
    if hyde_model:
        hyde_info["model"] = hyde_model
    hyde_weight = settings.get("HYDE_WEIGHT_QUESTION_MATCH")
    if hyde_weight is not None:
        try:
            hyde_info["weight"] = float(hyde_weight)
        except Exception:
            pass
    hyde_k_fraction = settings.get("HYDE_K_FRACTION")
    if hyde_k_fraction is not None:
        try:
            hyde_info["k_fraction"] = float(hyde_k_fraction)
        except Exception:
            pass

    health_status = {
        "status": "healthy" if EMBEDDINGS_AVAILABLE else "degraded",
        "service": "embeddings_v5_production_enhanced",
        "timestamp": datetime.utcnow().isoformat(),
        "cache_stats": embedding_cache.stats(),
        "active_requests": active_embedding_requests._value.get(),
        "circuit_breakers": breaker_status,
        "hyde": hyde_info,
    }

    if not EMBEDDINGS_AVAILABLE:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_status
        )

    return health_status

@router.get(
    "/embeddings/circuit-breakers",
    summary="Get circuit breaker status (admin only)"
)
async def get_circuit_breakers(
    current_user: User = Depends(get_request_user)
):
    """Get detailed circuit breaker status - requires admin privileges"""

    require_admin(current_user)

    return circuit_breaker_registry.get_all_status()

@router.post(
    "/embeddings/circuit-breakers/{provider}/reset",
    summary="Reset circuit breaker (admin only)"
)
async def reset_circuit_breaker(
    provider: str,
    current_user: User = Depends(get_request_user)
):
    """Reset specific circuit breaker - requires admin privileges"""

    require_admin(current_user)

    breaker_name = f"embeddings_{provider}"
    breaker = circuit_breaker_registry.get(breaker_name)

    if not breaker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker for provider '{provider}' not found"
        )

    breaker.reset()

    logger.info(
        f"Circuit breaker reset by admin",
        extra={
            "admin_id": current_user.id,
            "provider": provider
        }
    )

    return {
        "message": f"Circuit breaker for '{provider}' reset successfully"
    }

@router.get(
    "/embeddings/metrics",
    summary="Get service metrics (admin only)"
)
async def get_metrics(
    current_user: User = Depends(get_request_user)
):
    """Get detailed service metrics - requires admin privileges"""

    require_admin(current_user)

    # Helper to sum counters across all labels
    def _sum_counter(c):
        try:
            total = 0.0
            for metric in c.collect():
                for s in metric.samples:
                    # Only sum the main counter samples (exclude created/_total duplicates if any appear)
                    if s.name.endswith('_total') or s.name == metric.name:
                        total += float(s.value)
            return int(total)
        except Exception:
            return None

    def _safe_gauge_value(g):
        try:
            return g._value.get()
        except Exception:
            return None

    def _details(metric):
        try:
            samples = []
            for m in metric.collect():
                for s in m.samples:
                    entry = {"name": s.name, "value": float(s.value)}
                    try:
                        entry.update(s.labels)
                    except Exception:
                        pass
                    samples.append(entry)
            return samples
        except Exception:
            return []

    payload = {
        "cache": embedding_cache.stats(),
        "active_requests": _safe_gauge_value(active_embedding_requests),
        "circuit_breakers": circuit_breaker_registry.get_all_status(),
        "counters": {
            "requests_total": _sum_counter(embedding_requests_total),
            "provider_failures_total": _sum_counter(embedding_provider_failures),
            "fallbacks_total": _sum_counter(embedding_fallbacks_total),
            "policy_denied_total": _sum_counter(embedding_policy_denied_total),
            "dimension_adjustments_total": _sum_counter(embedding_dimension_adjustments_total),
            "token_inputs_total": _sum_counter(embedding_token_inputs_total),
        },
        "details": {
            "requests": _details(embedding_requests_total),
            "provider_failures": _details(embedding_provider_failures),
            "fallbacks": _details(embedding_fallbacks_total),
            "policy_denied": _details(embedding_policy_denied_total),
            "dimension_adjustments": _details(embedding_dimension_adjustments_total),
            "token_inputs": _details(embedding_token_inputs_total),
        },
        "config": {
            "enforce_policy": _should_enforce_policy(current_user),
            "dimension_policy": _dimension_policy(),
            "cache": {
                "ttl_seconds": CACHE_TTL_SECONDS,
                "max_size": MAX_CACHE_SIZE,
                "cleanup_interval": CACHE_CLEANUP_INTERVAL,
            }
        }
    }
    return payload


# ============================================================================
# DLQ Admin Endpoints
# ============================================================================

class DLQItem(BaseModel):
    entry_id: str = Field(..., description="Redis stream entry ID")
    queue: str = Field(..., description="DLQ stream name")
    job_id: Optional[str] = None
    error: Optional[str] = None
    failed_at: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    fields: Dict[str, Any] = Field(default_factory=dict)
    dlq_state: Optional[str] = None
    operator_note: Optional[str] = None


def _redact_obj(obj: Any, depth: int = 0) -> Any:
    """Redact likely PII/secrets from nested structures for previews."""
    if depth > 5:
        return obj
    SENSITIVE_KEYS = {"api_key", "authorization", "token", "password", "secret", "access_token", "id_token"}
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key_low = str(k).lower().replace("-", "_")
            if key_low in SENSITIVE_KEYS:
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact_obj(v, depth + 1)
        return out
    if isinstance(obj, list):
        return [_redact_obj(x, depth + 1) for x in obj]
    if isinstance(obj, str):
        if len(obj) > 12 and any(x in obj.lower() for x in ("sk-", "api_key", "bearer ")):
            return "***REDACTED***"
    return obj


@router.get(
    "/embeddings/dlq",
    summary="List DLQ items for a stage (admin only)"
)
async def list_dlq_items(
    stage: str = Query("embedding", description="Stage: chunking|embedding|storage"),
    count: int = Query(50, ge=1, le=500, description="Max items to return"),
    job_id: Optional[str] = Query(None, description="Optional job_id to filter"),
    current_user: User = Depends(get_request_user)
):
    require_admin(current_user)
    stream = _dlq_stream_name(stage)
    try:
        client = await _get_redis_client()
        # Reverse range: most recent first
        entries = await client.xrevrange(stream, "+", "-", count=count)
        items: List[DLQItem] = []
        for entry_id, fields in entries:
            # fields is a dict[str,str]
            payload = None
            try:
                raw_payload = fields.get("payload")
                if raw_payload:
                    payload = json.loads(raw_payload)
                elif fields.get("payload_enc"):
                    payload = decrypt_payload_if_present(fields.get("payload_enc"))
            except Exception:
                payload = None
            if payload is not None:
                payload = _redact_obj(payload)
            ji = fields.get("job_id")
            if job_id and ji != job_id:
                continue
            # sidecar state (quarantine/approval)
            dlq_state = None
            operator_note = None
            try:
                state_key = f"dlqstate:{stream}:{entry_id}"
                state_map = await client.hgetall(state_key)
                if isinstance(state_map, dict):
                    dlq_state = state_map.get("state") or fields.get("dlq_state")
                    operator_note = state_map.get("operator_note")
            except Exception:
                # Fallback to inline DLQ state fields if available
                dlq_state = fields.get("dlq_state")

            items.append(DLQItem(
                entry_id=entry_id,
                queue=stream,
                job_id=ji,
                error=fields.get("error"),
                failed_at=fields.get("failed_at"),
                payload=payload,
                fields=fields,
                dlq_state=dlq_state,
                operator_note=operator_note,
            ))
        await ensure_async_client_closed(client)
        return {"stream": stream, "count": len(items), "items": [i.model_dump() for i in items]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list DLQ items: {e}")


class DLQRequeueRequest(BaseModel):
    stage: str = Field(..., description="Stage: chunking|embedding|storage")
    entry_id: str = Field(..., description="Redis stream entry ID")
    delete_from_dlq: bool = Field(default=True)
    override_fields: Optional[Dict[str, Any]] = Field(default=None, description="Optional field overrides before requeue")


@router.post(
    "/embeddings/dlq/requeue",
    summary="Requeue a DLQ item to its live stream (admin only)"
)
async def requeue_dlq_item(
    req: DLQRequeueRequest,
    current_user: User = Depends(get_request_user)
):
    require_admin(current_user)
    dlq_stream = _dlq_stream_name(req.stage)
    live_stream = _live_stream_name(req.stage)
    client = await _get_redis_client()
    try:
        # Fetch the specific entry
        # XCLAIM not suitable; use XRANGE and filter by ID
        entries = await client.xrange(dlq_stream, min=req.entry_id, max=req.entry_id, count=1)
        if not entries:
            raise HTTPException(status_code=404, detail="DLQ entry not found")
        entry_id, fields = entries[0]
        # Quarantine enforcement: require approved_for_requeue if any state present
        try:
            st_map = await client.hgetall(f"dlqstate:{dlq_stream}:{entry_id}")
            effective_state = st_map.get("state") or fields.get("dlq_state")
        except Exception:
            effective_state = fields.get("dlq_state")
        if effective_state and effective_state not in ("approved_for_requeue",):
            dlq_requeued_total.labels(queue_name=dlq_stream, status="blocked").inc()
            raise HTTPException(status_code=400, detail=f"DLQ entry in state '{effective_state}', not approved for requeue")
        # Prepare requeue payload
        requeue_fields = dict(fields)
        warning = None
        # Validate original payload JSON (if present) and surface warnings
        try:
            raw = fields.get("payload")
            if raw:
                try:
                    original = json.loads(raw)
                except Exception:
                    original = None
                if isinstance(original, dict):
                    try:
                        validate_schema(req.stage, original)
                    except Exception as ve:
                        warning = f"payload schema validation failed: {ve}"
        except Exception:
            pass
        # Remove DLQ-specific fields
        for k in ["consumer_group", "worker_id", "failed_at", "error", "payload"]:
            requeue_fields.pop(k, None)
        if req.override_fields:
            requeue_fields.update(req.override_fields)
        # Requeue to live stream
        await client.xadd(live_stream, requeue_fields)
        # Optionally delete from DLQ
        if req.delete_from_dlq:
            try:
                await client.xdel(dlq_stream, entry_id)
            except Exception:
                pass
        dlq_requeued_total.labels(queue_name=dlq_stream, status="success").inc()
        out = {"message": "requeued", "from": dlq_stream, "to": live_stream, "entry_id": entry_id}
        if warning:
            out["warning"] = warning
        # Audit: DLQ requeue single
        try:
            svc = await get_audit_service_for_user(current_user)
            ctx = AuditContext(
                user_id=str(getattr(current_user, "id", "")),
                endpoint="/api/v1/embeddings/dlq/requeue",
                method="POST",
            )
            await svc.log_event(
                event_type=AuditEventType.DATA_UPDATE,
                category=AuditEventCategory.SECURITY,
                context=ctx,
                resource_type="dlq",
                resource_id=entry_id,
                action="requeue",
                metadata={"from": dlq_stream, "to": live_stream, "stage": req.stage, "warning": bool(warning)},
            )
        except Exception:
            pass
        return out
    except HTTPException:
        dlq_requeued_total.labels(queue_name=dlq_stream, status="not_found").inc()
        raise
    except Exception as e:
        dlq_requeue_errors_total.labels(queue_name=dlq_stream, error_type=type(e).__name__).inc()
        raise HTTPException(status_code=500, detail=f"Failed to requeue DLQ item: {e}")
    finally:
        await ensure_async_client_closed(client)


class DLQRequeueBulkRequest(BaseModel):
    stage: str
    entry_ids: List[str]
    delete_from_dlq: bool = True
    override_fields: Optional[Dict[str, Any]] = None


@router.post(
    "/embeddings/dlq/requeue/bulk",
    summary="Bulk requeue DLQ items to live stream (admin only)"
)
async def requeue_dlq_bulk(
    req: DLQRequeueBulkRequest,
    current_user: User = Depends(get_request_user)
):
    require_admin(current_user)
    dlq_stream = _dlq_stream_name(req.stage)
    live_stream = _live_stream_name(req.stage)
    client = await _get_redis_client()
    results: List[Dict[str, Any]] = []
    try:
        for eid in req.entry_ids:
            status = "success"
            try:
                entries = await client.xrange(dlq_stream, min=eid, max=eid, count=1)
                if not entries:
                    status = "not_found"
                else:
                    eid_found, fields = entries[0]
                    try:
                        st_map = await client.hgetall(f"dlqstate:{dlq_stream}:{eid_found}")
                        effective_state = st_map.get("state") or fields.get("dlq_state")
                    except Exception:
                        effective_state = fields.get("dlq_state")
                    if effective_state and effective_state not in ("approved_for_requeue",):
                        status = f"blocked:{effective_state}"
                        results.append({"entry_id": eid, "status": status})
                        continue
                    requeue_fields = dict(fields)
                    warning = None
                    # Validate original payload JSON (if present) and surface warnings
                    try:
                        raw = fields.get("payload")
                        if raw:
                            try:
                                original = json.loads(raw)
                            except Exception:
                                original = None
                            if isinstance(original, dict):
                                try:
                                    validate_schema(req.stage, original)
                                except Exception as ve:
                                    warning = f"payload schema validation failed: {ve}"
                    except Exception:
                        pass
                    for k in ["consumer_group", "worker_id", "failed_at", "error"]:
                        requeue_fields.pop(k, None)
                    requeue_fields.pop("payload", None)
                    if req.override_fields:
                        requeue_fields.update(req.override_fields)
                    await client.xadd(live_stream, requeue_fields)
                    if req.delete_from_dlq:
                        try:
                            await client.xdel(dlq_stream, eid)
                        except Exception:
                            pass
            except Exception as e:
                status = f"error:{type(e).__name__}"
                dlq_requeue_errors_total.labels(queue_name=dlq_stream, error_type=type(e).__name__).inc()
            else:
                dlq_requeued_total.labels(queue_name=dlq_stream, status=status).inc()
            res = {"entry_id": eid, "status": status}
            if 'warning' in locals() and warning:
                res["warning"] = warning
            results.append(res)
        # Audit: DLQ bulk requeue summary
        try:
            svc = await get_audit_service_for_user(current_user)
            ctx = AuditContext(
                user_id=str(getattr(current_user, "id", "")),
                endpoint="/api/v1/embeddings/dlq/requeue/bulk",
                method="POST",
            )
            counts = {"success": 0, "not_found": 0, "blocked": 0, "error": 0}
            for r in results:
                st = str(r.get("status", "success"))
                if st.startswith("blocked"):
                    counts["blocked"] += 1
                elif st in counts:
                    counts[st] += 1
                elif st.startswith("error"):
                    counts["error"] += 1
            await svc.log_event(
                event_type=AuditEventType.DATA_UPDATE,
                category=AuditEventCategory.SECURITY,
                context=ctx,
                resource_type="dlq",
                resource_id=dlq_stream,
                action="bulk_requeue",
                metadata={"stage": req.stage, **counts, "total": len(req.entry_ids)},
            )
        except Exception:
            pass
        return {"from": dlq_stream, "to": live_stream, "results": results}
    finally:
        await ensure_async_client_closed(client)


@router.get(
    "/embeddings/dlq/stats",
    summary="DLQ and queue depths (admin only)"
)
async def get_dlq_stats(
    current_user: User = Depends(get_request_user)
):
    require_admin(current_user)
    client = await _get_redis_client()
    try:
        queues = ["embeddings:chunking", "embeddings:embedding", "embeddings:storage"]
        depths = {}
        dlq_depths = {}
        for q in queues:
            try:
                depths[q] = await client.xlen(q)
            except Exception:
                depths[q] = 0
            dq = f"{q}:dlq"
            try:
                dlq_depths[dq] = await client.xlen(dq)
            except Exception:
                dlq_depths[dq] = 0
        total_dlq = sum(dlq_depths.values())

        # Aggregate worker metrics to summarize stage processed/failed
        stages = {"chunking": {"processed": 0, "failed": 0},
                  "embedding": {"processed": 0, "failed": 0},
                  "storage": {"processed": 0, "failed": 0}}
        try:
            cursor = 0
            processed = 0
            while True:
                cursor, keys = await client.scan(cursor, match="worker:metrics:*", count=100)
                for k in keys:
                    if processed >= ORCH_SCAN_MAX_KEYS:
                        cursor = 0
                        break
                    data = await client.get(k)
                    processed += 1
                    if not data:
                        continue
                    try:
                        m = json.loads(data)
                        stage = str(m.get("worker_type", "")).lower()
                        proc = int(m.get("jobs_processed", 0) or 0)
                        fail = int(m.get("jobs_failed", 0) or 0)
                        if stage in stages:
                            stages[stage]["processed"] += proc
                            stages[stage]["failed"] += fail
                    except Exception:
                        continue
                if cursor == 0:
                    break
        except Exception:
            pass

        return {"queues": depths, "dlq": dlq_depths, "total_dlq": total_dlq, "stages": stages}
    finally:
        await ensure_async_client_closed(client)


# ---------------------------------------------------------------------------
# DLQ Quarantine State Management (admin only)
# ---------------------------------------------------------------------------

class DLQStateSetRequest(BaseModel):
    stage: str
    entry_id: str
    state: str  # quarantined | approved_for_requeue | ignored
    operator_note: Optional[str] = None


def _dlq_state_key(stream: str, entry_id: str) -> str:
    return f"dlqstate:{stream}:{entry_id}"


@router.post(
    "/embeddings/dlq/state",
    summary="Set DLQ quarantine state (admin only)"
)
async def set_dlq_state(req: DLQStateSetRequest, current_user: User = Depends(get_request_user)):
    require_admin(current_user)
    client = await _get_redis_client()
    try:
        dlq_stream = _dlq_stream_name(req.stage)
        # Validate entry exists
        entries = await client.xrange(dlq_stream, min=req.entry_id, max=req.entry_id, count=1)
        if not entries:
            raise HTTPException(status_code=404, detail="DLQ entry not found")
        st = (req.state or "").strip().lower()
        if st not in ("quarantined", "approved_for_requeue", "ignored"):
            raise HTTPException(status_code=400, detail="Invalid state")
        if st == "approved_for_requeue" and not (req.operator_note and req.operator_note.strip()):
            raise HTTPException(status_code=400, detail="operator_note is required to approve requeue")
        val = {
            "state": st,
            "operator_note": req.operator_note or "",
            "updated_by": getattr(current_user, "username", "admin"),
            "updated_at": datetime.utcnow().isoformat(),
        }
        await client.hset(_dlq_state_key(dlq_stream, req.entry_id), mapping=val)
        # Audit: DLQ quarantine state change
        try:
            svc = await get_audit_service_for_user(current_user)
            ctx = AuditContext(
                user_id=str(getattr(current_user, "id", "")),
                endpoint="/api/v1/embeddings/dlq/state",
                method="POST",
            )
            await svc.log_event(
                event_type=AuditEventType.DATA_UPDATE,
                category=AuditEventCategory.SECURITY,
                context=ctx,
                resource_type="dlq",
                resource_id=req.entry_id,
                action="quarantine_state",
                metadata={"stage": req.stage, "state": st, "operator_note": req.operator_note or ""},
            )
        except Exception:
            pass
        return {"ok": True, "stream": dlq_stream, "entry_id": req.entry_id, "state": st}
    finally:
        await ensure_async_client_closed(client)


# ---------------------------------------------------------------------------
# Stage Controls: pause/resume/drain per stage (admin only)
# ---------------------------------------------------------------------------

class StageControlRequest(BaseModel):
    stage: str  # chunking|embedding|storage|all
    action: str  # pause|resume|drain


def _stage_key(stage: str, suffix: str) -> str:
    stage = stage.strip().lower()
    if stage not in {"chunking", "embedding", "storage"}:
        raise HTTPException(status_code=400, detail="Invalid stage; must be chunking|embedding|storage")
    return f"embeddings:stage:{stage}:{suffix}"


@router.get(
    "/embeddings/stage/status",
    summary="Get per-stage pause/drain flags (admin only)"
)
async def get_stage_status(current_user: User = Depends(get_request_user)):
    require_admin(current_user)
    client = await _get_redis_client()
    try:
        out = {}
        for st in ("chunking", "embedding", "storage"):
            paused = await client.get(_stage_key(st, "paused"))
            drain = await client.get(_stage_key(st, "drain"))
            out[st] = {
                "paused": str(paused).lower() in ("1", "true", "yes"),
                "drain": str(drain).lower() in ("1", "true", "yes"),
            }
        return out
    finally:
        await ensure_async_client_closed(client)


@router.post(
    "/embeddings/stage/control",
    summary="Pause/Resume/Drain a stage (admin only)"
)
async def control_stage(req: StageControlRequest, current_user: User = Depends(get_request_user)):
    require_admin(current_user)
    client = await _get_redis_client()
    try:
        stages = [req.stage] if req.stage != "all" else ["chunking", "embedding", "storage"]
        for st in stages:
            if req.action == "pause":
                await client.set(_stage_key(st, "paused"), "1")
            elif req.action == "resume":
                await client.delete(_stage_key(st, "paused"))
                await client.delete(_stage_key(st, "drain"))
            elif req.action == "drain":
                # Mark drain intent and pause new reads; in-flight items will finish
                await client.set(_stage_key(st, "drain"), "1")
                await client.set(_stage_key(st, "paused"), "1")
            else:
                raise HTTPException(status_code=400, detail="Invalid action; must be pause|resume|drain")
        # Audit
        try:
            svc = await get_audit_service_for_user(current_user)
            ctx = AuditContext(
                user_id=str(getattr(current_user, "id", "")),
                endpoint="/api/v1/embeddings/stage/control",
                method="POST",
            )
            await svc.log_event(
                event_type=AuditEventType.CONFIG_CHANGED,
                category=AuditEventCategory.SYSTEM,
                context=ctx,
                resource_type="embeddings_stage",
                resource_id=",".join(stages),
                action=req.action,
                metadata={"stages": stages, "action": req.action},
            )
        except Exception:
            pass
        return {"ok": True, "stages": stages, "action": req.action}
    finally:
        await ensure_async_client_closed(client)


# ---------------------------------------------------------------------------
# Job skip registry (admin only)
# ---------------------------------------------------------------------------

class JobSkipRequest(BaseModel):
    job_id: str
    ttl_seconds: Optional[int] = Field(default=7 * 24 * 3600, ge=60, description="TTL for skip registry entry")


def _skip_key(job_id: str) -> str:
    return f"embeddings:skip:job:{job_id}"


@router.post(
    "/embeddings/job/skip",
    summary="Mark a job_id as skipped (admin only)"
)
async def mark_job_skipped(req: JobSkipRequest, current_user: User = Depends(get_request_user)):
    require_admin(current_user)
    client = await _get_redis_client()
    try:
        await client.set(_skip_key(req.job_id), "1", ex=int(req.ttl_seconds))
        # Audit
        try:
            svc = await get_audit_service_for_user(current_user)
            ctx = AuditContext(
                user_id=str(getattr(current_user, "id", "")),
                endpoint="/api/v1/embeddings/job/skip",
                method="POST",
            )
            await svc.log_event(
                event_type=AuditEventType.DATA_UPDATE,
                category=AuditEventCategory.SECURITY,
                context=ctx,
                resource_type="job",
                resource_id=req.job_id,
                action="skip",
                metadata={"ttl_seconds": int(req.ttl_seconds or 0)},
            )
        except Exception:
            pass
        return {"ok": True, "job_id": req.job_id, "ttl_seconds": req.ttl_seconds}
    finally:
        await ensure_async_client_closed(client)


@router.get(
    "/embeddings/job/skip/status",
    summary="Check if a job_id is marked as skipped (admin only)"
)
async def get_job_skip_status(job_id: str = Query(..., description="Job ID to check"), current_user: User = Depends(get_request_user)):
    require_admin(current_user)
    client = await _get_redis_client()
    try:
        val = await client.get(_skip_key(job_id))
        return {"job_id": job_id, "skipped": str(val).lower() in ("1", "true", "yes")}
    finally:
        await ensure_async_client_closed(client)


# ---------------------------------------------------------------------------
# Ledger Admin Endpoints (idempotency/dedupe)
# ---------------------------------------------------------------------------

class LedgerEntry(BaseModel):
    key: str
    status: Optional[str] = None
    ts: Optional[int] = None
    job_id: Optional[str] = None
    raw: Optional[Union[Dict[str, Any], str]] = None
    ttl_seconds: Optional[int] = None


@router.get(
    "/embeddings/ledger/status",
    summary="Inspect ledger entries by idempotency_key/dedupe_key (admin only)"
)
async def get_ledger_status(
    idempotency_key: Optional[str] = Query(default=None),
    dedupe_key: Optional[str] = Query(default=None),
    current_user: User = Depends(get_request_user),
):
    """Return current ledger values for provided keys.

    Reads:
      - embeddings:ledger:idemp:{idempotency_key}
      - embeddings:ledger:dedupe:{dedupe_key}
    Values may be plain strings or JSON objects with {status, ts, job_id}.
    """
    require_admin(current_user)
    if not idempotency_key and not dedupe_key:
        raise HTTPException(status_code=400, detail="Provide idempotency_key and/or dedupe_key")
    client = await _get_redis_client()
    try:
        out: Dict[str, Optional[LedgerEntry]] = {"idempotency": None, "dedupe": None}
        if idempotency_key:
            k = f"embeddings:ledger:idemp:{idempotency_key}"
            raw = await client.get(k)
            ttl = await client.ttl(k)
            entry = LedgerEntry(key=k, ttl_seconds=(int(ttl) if isinstance(ttl, (int, float)) else None))
            if raw is not None:
                try:
                    obj = json.loads(raw)
                    entry.status = str(obj.get("status")) if isinstance(obj, dict) else None
                    entry.ts = int(obj.get("ts")) if isinstance(obj, dict) and obj.get("ts") is not None else None
                    entry.job_id = str(obj.get("job_id")) if isinstance(obj, dict) else None
                    entry.raw = obj if isinstance(obj, dict) else raw
                except Exception:
                    entry.raw = raw
                    entry.status = str(raw)
            out["idempotency"] = entry
        if dedupe_key:
            k = f"embeddings:ledger:dedupe:{dedupe_key}"
            raw = await client.get(k)
            ttl = await client.ttl(k)
            entry = LedgerEntry(key=k, ttl_seconds=(int(ttl) if isinstance(ttl, (int, float)) else None))
            if raw is not None:
                try:
                    obj = json.loads(raw)
                    entry.status = str(obj.get("status")) if isinstance(obj, dict) else None
                    entry.ts = int(obj.get("ts")) if isinstance(obj, dict) and obj.get("ts") is not None else None
                    entry.job_id = str(obj.get("job_id")) if isinstance(obj, dict) else None
                    entry.raw = obj if isinstance(obj, dict) else raw
                except Exception:
                    entry.raw = raw
                    entry.status = str(raw)
            out["dedupe"] = entry
        return out
    finally:
        await ensure_async_client_closed(client)


# ---------------------------------------------------------------------------
# Re-embed Scheduling (admin only)
# ---------------------------------------------------------------------------

class ReembedScheduleRequest(BaseModel):
    media_id: int = Field(..., description="Target media_id to re-embed")
    user_id: Optional[str] = Field(default=None, description="Owner user id; defaults to current admin")
    idempotency_key: Optional[str] = Field(default=None, description="Optional idempotency key to dedupe creation")
    dedupe_key: Optional[str] = Field(default=None, description="Optional dedupe key; defaults to idempotency_key if not provided")
    operation_id: Optional[str] = Field(default=None, description="Optional operation id for replay prevention")
    priority: Optional[int] = Field(default=50, ge=0, le=100)
    user_tier: Optional[str] = Field(default="free")
    embedder_name: Optional[str] = None
    embedder_version: Optional[str] = None


class ReembedScheduleResponse(BaseModel):
    id: int
    uuid: Optional[str] = None
    status: str
    domain: str
    queue: str
    job_type: str


@router.post(
    "/embeddings/reembed/schedule",
    response_model=ReembedScheduleResponse,
    summary="Schedule a re-embed expansion job (admin only)"
)
async def schedule_reembed(
    req: ReembedScheduleRequest,
    current_user: User = Depends(get_request_user),
    request: Request = None,
):
    """Create a Jobs row for the re-embed expansion worker to process.

    Domain: embeddings, Queue: reembed (configurable via REEMBED_JOB_QUEUE), Job Type: expand_reembed.
    """
    require_admin(current_user)
    # Build payload
    uid = str(req.user_id or current_user.id)
    payload = {
        "user_id": uid,
        "media_id": int(req.media_id),
        "idempotency_key": req.idempotency_key,
        "dedupe_key": req.dedupe_key,
        "operation_id": req.operation_id,
        "user_tier": req.user_tier or "free",
        "embedder_name": req.embedder_name,
        "embedder_version": req.embedder_version,
    }
    # Construct default idempotency/dedupe if not provided
    if not req.idempotency_key:
        payload["idempotency_key"] = f"reembed:{uid}:{int(req.media_id)}:{req.embedder_name or ''}:{req.embedder_version or ''}"
    if not req.dedupe_key:
        payload["dedupe_key"] = payload["idempotency_key"]

    # Create job via JobManager
    try:
        from tldw_Server_API.app.core.Jobs.manager import JobManager  # local import to avoid hard dep at import-time
        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        jm = JobManager(backend=backend, db_url=db_url)
        queue = os.getenv("REEMBED_JOB_QUEUE", "reembed")
        rid = ensure_request_id(request) if request is not None else None
        tp = ensure_traceparent(request) if request is not None else ""
        row = jm.create_job(
            domain="embeddings",
            queue=queue,
            job_type="expand_reembed",
            payload=payload,
            owner_user_id=uid,
            priority=int(req.priority or 50),
            idempotency_key=payload.get("idempotency_key"),
            request_id=rid,
        )
        get_ps_logger(request_id=rid, ps_component="endpoint", ps_job_kind="reembed", traceparent=tp).info(
            "Scheduled re-embed job: job_id=%s media_id=%s", row.get("id"), payload.get("media_id")
        )
        return ReembedScheduleResponse(
            id=int(row.get("id")),
            uuid=row.get("uuid"),
            status=str(row.get("status")),
            domain=str(row.get("domain")),
            queue=str(row.get("queue")),
            job_type=str(row.get("job_type")),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule re-embed: {e}")


# ---------------------------------------------------------------------------
# Orchestrator snapshot + SSE (admin only)
# ---------------------------------------------------------------------------

async def _build_orchestrator_snapshot(client: aioredis.Redis, now_ts: Optional[float] = None) -> Dict[str, Any]:
    """Compute a single orchestrator snapshot.

    Returns dict with keys: queues, dlq, ages, stages, flags, ts
    """
    from time import time as _now
    if now_ts is None:
        now_ts = _now()

    # Build the same structure as get_dlq_stats and add queue ages and stage flags
    queues = ["embeddings:chunking", "embeddings:embedding", "embeddings:storage"]
    depths: Dict[str, int] = {}
    dlq_depths: Dict[str, int] = {}
    ages: Dict[str, float] = {}
    # Optional per-priority depths when priority routing is enabled
    priority_enabled = str(os.getenv("EMBEDDINGS_PRIORITY_ENABLED", "false")).lower() in ("1", "true", "yes")
    priority_depths: Dict[str, Dict[str, int]] = {"chunking": {}, "embedding": {}, "storage": {}}
    for q in queues:
        try:
            depths[q] = await client.xlen(q)
        except Exception:
            depths[q] = 0
        # Expose per-priority sub-queue depths (high/normal/low)
        if priority_enabled:
            stage = q.split(":", 1)[1]
            for pr in ("high", "normal", "low"):
                sub = f"{q}:{pr}"
                try:
                    dsub = await client.xlen(sub)
                except Exception:
                    dsub = 0
                depths[sub] = dsub
                priority_depths[stage][pr] = dsub
        # queue age (oldest entry)
        try:
            rng = await client.xrange(q, min='-', max='+', count=1)
            if rng:
                first_id, _ = rng[0]
                ts_ms = int(str(first_id).split('-')[0])
                ages[q] = max(0.0, (now_ts * 1000 - ts_ms) / 1000.0)
            else:
                ages[q] = 0.0
        except Exception:
            ages[q] = 0.0
        dq = f"{q}:dlq"
        try:
            dlq_depths[dq] = await client.xlen(dq)
        except Exception:
            dlq_depths[dq] = 0
        try:
            embedding_queue_age_current_seconds.labels(queue_name=q).set(float(ages.get(q, 0.0)))
        except Exception:
            pass

    # stage counters (aggregate from worker snapshots)
    stages: Dict[str, Dict[str, int]] = {
        "chunking": {"processed": 0, "failed": 0},
        "embedding": {"processed": 0, "failed": 0},
        "storage": {"processed": 0, "failed": 0},
    }
    try:
        cursor = 0
        processed = 0
        while True:
            cursor, keys = await client.scan(cursor, match="worker:metrics:*", count=100)
            for k in keys:
                if processed >= ORCH_SCAN_MAX_KEYS:
                    cursor = 0
                    break
                data = await client.get(k)
                processed += 1
                if not data:
                    continue
                try:
                    m = json.loads(data)
                    st = str(m.get("worker_type", "")).lower()
                    if st in stages:
                        stages[st]["processed"] += int(m.get("jobs_processed", 0) or 0)
                        stages[st]["failed"] += int(m.get("jobs_failed", 0) or 0)
                except Exception:
                    continue
            if cursor == 0:
                break
    except Exception:
        pass

    # stage flags
    flags: Dict[str, Dict[str, bool]] = {}
    for st in ("chunking", "embedding", "storage"):
        p = await client.get(f"embeddings:stage:{st}:paused")
        d = await client.get(f"embeddings:stage:{st}:drain")
        flags[st] = {
            "paused": str(p).lower() in ("1", "true", "yes"),
            "drain": str(d).lower() in ("1", "true", "yes"),
        }
        try:
            embedding_stage_flag.labels(stage=st, flag="paused").set(1.0 if flags[st]["paused"] else 0.0)
            embedding_stage_flag.labels(stage=st, flag="drain").set(1.0 if flags[st]["drain"] else 0.0)
        except Exception:
            pass

    return {"queues": depths, "dlq": dlq_depths, "ages": ages, "stages": stages, "flags": flags, "priority": priority_depths if priority_enabled else {}, "ts": now_ts}


async def _sse_orchestrator_stream(client: aioredis.Redis):
    import asyncio as _asyncio
    import random as _random
    while True:
        try:
            payload = await _build_orchestrator_snapshot(client)
            data = json.dumps(payload)
            # Emit event type for clients that use it
            yield f"event: summary\ndata: {data}\n\n"
            # Optional heartbeat comment
            yield ":\n\n"
            # Jittered interval around 5s
            await _asyncio.sleep(_random.uniform(4.5, 5.5))
        except Exception as e:
            # keep the stream alive; emit error info once
            try:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            except Exception:
                pass
            await _asyncio.sleep(_random.uniform(4.5, 5.5))


@router.get(
    "/embeddings/orchestrator/events",
    summary="SSE: embeddings orchestrator live summary (admin only)"
)
async def orchestrator_events(current_user: User = Depends(get_request_user)):
    require_admin(current_user)
    client = await _get_redis_client()
    async def _gen():
        try:
            orchestrator_sse_connections.inc()
            async for chunk in _sse_orchestrator_stream(client):
                yield chunk
        finally:
            try:
                orchestrator_sse_connections.dec()
                orchestrator_sse_disconnects_total.inc()
            except Exception:
                pass
            await ensure_async_client_closed(client)
    # The client will keep the connection; we don't close Redis here (shared)
    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get(
    "/embeddings/orchestrator/summary",
    summary="Orchestrator summary for polling (admin only)"
)
async def orchestrator_summary(current_user: User = Depends(get_request_user)):
    """Return a snapshot identical to the SSE payload.

    Includes: queues, dlq, ages, stages, flags, ts
    """
    require_admin(current_user)
    client: Optional[aioredis.Redis] = None
    def _zero_snapshot() -> Dict[str, Any]:
        return {"queues": {}, "dlq": {}, "ages": {}, "stages": {}, "flags": {}, "ts": datetime.utcnow().timestamp()}

    try:
        client = await _get_redis_client()
        if getattr(client, "_tldw_is_stub", False):
            try:
                orchestrator_summary_failures_total.inc()
            except Exception:
                pass
            snapshot = _zero_snapshot()
            await ensure_async_client_closed(client)
            client = None
            return snapshot
    except Exception:
        try:
            orchestrator_summary_failures_total.inc()
        except Exception:
            pass
        return _zero_snapshot()
    try:
        return await _build_orchestrator_snapshot(client)
    except Exception:
        try:
            orchestrator_summary_failures_total.inc()
        except Exception:
            pass
        return _zero_snapshot()
    finally:
        await ensure_async_client_closed(client)
