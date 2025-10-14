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

import asyncio
import base64
import hashlib
import time
from datetime import datetime, timedelta
from typing import List, Union, Optional, Dict, Any, Tuple
from enum import Enum
import numpy as np
from functools import lru_cache, wraps
import atexit
import os

from fastapi import APIRouter, HTTPException, Body, Depends, status, BackgroundTasks, Request, Query, Header, Response
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
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
from slowapi import Limiter
from slowapi.util import get_remote_address

# Monitoring
from prometheus_client import Counter, Histogram, Gauge
from fnmatch import fnmatch

# ============================================================================
# Embeddings Implementation Import (Safe/Lazy)
# Avoid hard-failing on import so non-embedding tests can import the app.
# ============================================================================

try:
    from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
        create_embeddings_batch,
        EmbeddingConfigSchema,
        HFModelCfg,
        ONNXModelCfg,
        OpenAIModelCfg,
        LocalAPICfg
    )
    EMBEDDINGS_AVAILABLE = True
except Exception as e:
    # Do not raise here; allow the API to import and mark the embeddings service as unavailable.
    logger.error(f"Embeddings implementation unavailable: {e}")
    logger.error("Embeddings endpoints will respond 503 until dependencies are installed")
    EMBEDDINGS_AVAILABLE = False

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
        "sentence-transformers/all-mpnet-base-v2"
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

# ============================================================================
# Enhanced TTL Cache with Better Cleanup
# ============================================================================

class TTLCache:
    """Thread-safe cache with TTL support and automatic cleanup"""
    
    def __init__(self, max_size: int = MAX_CACHE_SIZE, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = Lock()
        self.cleanup_task = None
        self.hits = 0
        self.misses = 0
        
    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
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
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
                
    async def cleanup_expired(self):
        """Remove expired entries from cache"""
        async with self.lock:
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
                
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        async with self.lock:
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
        async with self.lock:
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
        async with self.lock:
            self.cache.clear()
            embedding_cache_size.set(0)
            self.hits = 0
            self.misses = 0
            
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
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
        if self._closed:
            raise RuntimeError("ConnectionPoolManager has been closed")
            
        async with self.lock:
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
limiter = Limiter(key_func=get_remote_address)

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
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            # Stop TTL cache cleanup task if running
            try:
                loop.run_until_complete(embedding_cache.stop_cleanup_task())
            except Exception:
                pass
            # Close provider connection pools
            loop.run_until_complete(connection_manager.close_all())
    except Exception as e:
        logger.error(f"Error during exit cleanup: {e}")

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
    # Admin bypass unless strict enforcement requested
    try:
        if user and getattr(user, 'is_admin', False) and os.getenv("EMBEDDINGS_ENFORCE_POLICY_STRICT", "false").lower() not in ("true", "1", "yes"):
            return False
    except Exception:
        pass
    try:
        cfg_val = settings.get("EMBEDDINGS_ENFORCE_POLICY", None)
        if isinstance(cfg_val, bool):
            return cfg_val
    except Exception:
        pass
    # If env explicitly set, honor it; otherwise, default to enforcing in TESTING for backward-compatibility
    env_val = os.getenv("EMBEDDINGS_ENFORCE_POLICY")
    if env_val is not None:
        return env_val.lower() in ("true", "1", "yes")
    if os.getenv("TESTING", "").lower() in ("true", "1", "yes"):
        return True
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
    config: Dict[str, Any]
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
            
            # Wrap config in expected structure for create_embeddings_batch
            app_config = {
                "embedding_config": {
                    "default_model_id": model_id,
                    "model_storage_base_dir": "./models/embedding_models_data/",
                    "models": {model_id: model_cfg},
                }
            }
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                create_embeddings_batch,
                texts,
                app_config,  # Pass wrapped config
                model_id
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
    api_url: Optional[str] = None
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
                        config
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
    
    try:
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
            # Disable fallback when x-provider header is explicitly set
            fallback_disabled = x_provider is not None
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
                        dimensions=embedding_request.dimensions
                    )
                    provider = p
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
    current_user: User = Depends(get_request_user)
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

    embeddings = await create_embeddings_batch_async(
        texts=texts,
        provider=provider,
        model_id=model,
        dimensions=payload.dimensions
    )

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

    try:
        vectors = await create_embeddings_batch_async(
            texts=["model probe"],
            provider=resolved_provider,
            model_id=model
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
    try:
        await create_embeddings_batch_async(
            texts=["model warmup test"],
            provider=provider,
            model_id=payload.model
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
    try:
        # Trigger a load without depending on real content by generating a small embedding
        await create_embeddings_batch_async(
            texts=["download model"],
            provider=provider,
            model_id=payload.model
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
            model_id=model
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
    
    health_status = {
        "status": "healthy" if EMBEDDINGS_AVAILABLE else "degraded",
        "service": "embeddings_v5_production_enhanced",
        "timestamp": datetime.utcnow().isoformat(),
        "cache_stats": embedding_cache.stats(),
        "active_requests": active_embedding_requests._value.get(),
        "circuit_breakers": breaker_status
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
