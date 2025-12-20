"""
Embeddings audit adapter

Bridges legacy Embeddings audit calls to the unified audit service without
requiring FastAPI dependency injection at call sites. Exposes small, sync-friendly
wrappers that schedule async logging tasks on the running event loop.
"""

from __future__ import annotations

import asyncio
import threading
import weakref
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import os
import atexit
import warnings

from loguru import logger

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    UnifiedAuditService,
    AuditEventType as UEvent,
    AuditContext,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


# LRU cache for audit services with configurable max size
_MAX_CACHED_SERVICES = int(os.getenv("EMBEDDINGS_AUDIT_MAX_CACHED_SERVICES", "20"))


@dataclass
class _LoopState:
    """Per-event-loop cache state to avoid cross-loop asyncio primitive issues."""

    cache: "OrderedDict[str, UnifiedAuditService]" = field(default_factory=OrderedDict)
    services_stopping: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_STATE_LOCK = threading.Lock()
_STATE_BY_LOOP: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _LoopState]" = weakref.WeakKeyDictionary()

_SYNC_LOOP: Optional[asyncio.AbstractEventLoop] = None
_SYNC_LOOP_THREAD: Optional[threading.Thread] = None
_SYNC_LOOP_LOCK = threading.Lock()
_SYNC_LOOP_READY = threading.Event()


def _state_for_loop() -> _LoopState:
    """Return per-loop adapter state (creates it lazily on first use)."""
    loop = asyncio.get_running_loop()
    with _STATE_LOCK:
        state = _STATE_BY_LOOP.get(loop)
        if state is None:
            state = _LoopState()
            _STATE_BY_LOOP[loop] = state
        return state


def _key_for_user(user_id: Optional[str]) -> str:
    return str(user_id) if user_id is not None else "__default__"


def _in_test_mode() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TEST_MODE") or os.getenv("TLDW_TEST_MODE"))


def _ensure_sync_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Ensure a background event loop exists for sync/threadpool calls."""
    global _SYNC_LOOP, _SYNC_LOOP_THREAD
    with _SYNC_LOOP_LOCK:
        if (
            _SYNC_LOOP_THREAD
            and _SYNC_LOOP_THREAD.is_alive()
            and _SYNC_LOOP
            and _SYNC_LOOP.is_running()
        ):
            return _SYNC_LOOP

        _SYNC_LOOP = None
        _SYNC_LOOP_READY.clear()

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            global _SYNC_LOOP
            _SYNC_LOOP = loop
            _SYNC_LOOP_READY.set()
            loop.run_forever()
            loop.close()

        _SYNC_LOOP_THREAD = threading.Thread(
            target=_run,
            name="embeddings-audit-sync-loop",
            daemon=True,
        )
        _SYNC_LOOP_THREAD.start()

    if not _SYNC_LOOP_READY.wait(timeout=1.0):
        return None
    return _SYNC_LOOP


def _stop_sync_loop() -> None:
    """Stop the background sync loop if running."""
    global _SYNC_LOOP, _SYNC_LOOP_THREAD
    loop = _SYNC_LOOP
    thread = _SYNC_LOOP_THREAD

    if loop and loop.is_running():
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass

    if thread and thread.is_alive() and threading.current_thread() is not thread:
        thread.join(timeout=2.0)

    _SYNC_LOOP = None
    _SYNC_LOOP_THREAD = None
    _SYNC_LOOP_READY.clear()


async def _evict_oldest_service(state: _LoopState) -> None:
    """Evict the oldest (least recently used) service from cache.

    Must be called while holding state.lock.
    """
    if not state.cache:
        return

    # Pop oldest item (first in OrderedDict)
    oldest_key, oldest_svc = state.cache.popitem(last=False)
    state.services_stopping.add(oldest_key)

    try:
        await oldest_svc.stop()
    except Exception as e:
        logger.debug(f"Error stopping evicted audit service for {oldest_key}: {e}")
    finally:
        state.services_stopping.discard(oldest_key)


async def _get_service_for_user(user_id: Optional[str]) -> UnifiedAuditService:
    """Get or initialize a cached unified audit service with LRU eviction.

    If a numeric user_id is provided, use the per-user audit DB path; otherwise,
    fallback to the default unified audit DB file.
    """
    key = _key_for_user(user_id)
    state = _state_for_loop()
    async with state.lock:
        # Check if this key is being stopped; wait briefly if so
        if key in state.services_stopping:
            # Rare edge case: service being evicted, return new one after lock release
            pass
        elif key in state.cache:
            # Move to end (most recently used)
            state.cache.move_to_end(key)
            return state.cache[key]

        # Evict oldest if at capacity
        while len(state.cache) >= _MAX_CACHED_SERVICES:
            await _evict_oldest_service(state)

        # Determine DB path
        db_path: Optional[str] = None
        if user_id is not None:
            try:
                uid_int = int(user_id)
                db_path = str(DatabasePaths.get_audit_db_path(uid_int))
            except Exception:
                # Non-numeric user; use default path
                db_path = None

        svc = UnifiedAuditService(db_path=db_path)
        await svc.initialize()
        state.cache[key] = svc
        return svc


async def _emit(
    user_id: Optional[str],
    event_type: UEvent,
    *,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    result: str = "success",
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
) -> None:
    try:
        svc = await _get_service_for_user(user_id)
        ctx = AuditContext(
            user_id=str(user_id) if user_id is not None else None,
            ip_address=ip_address,
            endpoint=endpoint,
            method=method,
        )
        await svc.log_event(
            event_type=event_type,
            context=ctx,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            metadata=metadata,
        )
        # In test environments, flush immediately to make events visible to queries
        # without relying on background flush loops.
        try:
            if _in_test_mode():
                await svc.flush()
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Embeddings audit emit failed: {e}")


def _schedule(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
        return
    except RuntimeError:
        pass

    loop = _ensure_sync_loop()
    if loop is None:
        # No loop available; suppress "coroutine never awaited" warning and close
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="coroutine.*was never awaited")
            try:
                coro.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        return

    try:
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="coroutine.*was never awaited")
            try:
                coro.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        return

    def _log_failure(done_fut) -> None:
        try:
            exc = done_fut.exception()
            if exc:
                logger.warning(f"Embeddings audit sync task failed: {exc}")
        except Exception:
            pass

    fut.add_done_callback(_log_failure)
    if _in_test_mode():
        try:
            fut.result(timeout=5)
        except Exception as e:
            logger.warning(f"Embeddings audit sync task timed out: {e}")


def log_security_violation(
    *, user_id: Optional[str], action: str, metadata: Optional[Dict[str, Any]] = None, ip_address: Optional[str] = None
) -> None:
    """Log a security violation (sync wrapper)."""
    _schedule(_emit(user_id, UEvent.SECURITY_VIOLATION, action=action, result="failure", metadata=metadata, ip_address=ip_address))


def log_model_evicted(*, model_id: str, memory_usage_gb: Optional[float] = None, reason: Optional[str] = None) -> None:
    """Log a model eviction as a data deletion event."""
    meta = {"memory_usage_gb": memory_usage_gb, "reason": reason}
    _schedule(_emit(None, UEvent.DATA_DELETE, action="model_evicted", resource_type="embedding_model", resource_id=model_id, metadata=meta))


def log_memory_limit_exceeded(
    *, model_id: str, memory_usage_gb: Optional[float], current_usage_gb: Optional[float], limit_gb: Optional[float]
) -> None:
    """Log memory limit exceeded as a system error event."""
    meta = {
        "memory_usage_gb": memory_usage_gb,
        "current_usage_gb": current_usage_gb,
        "limit_gb": limit_gb,
    }
    _schedule(_emit(None, UEvent.SYSTEM_ERROR, action="embeddings_memory_limit_exceeded", resource_type="embedding_model", resource_id=model_id, result="failure", metadata=meta))


# Async variants for tests
async def emit_security_violation_async(user_id: Optional[str], action: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    await _emit(user_id, UEvent.SECURITY_VIOLATION, action=action, result="failure", metadata=metadata)


async def emit_model_evicted_async(model_id: str, memory_usage_gb: Optional[float] = None, reason: Optional[str] = None) -> None:
    await _emit(None, UEvent.DATA_DELETE, action="model_evicted", resource_type="embedding_model", resource_id=model_id, metadata={"memory_usage_gb": memory_usage_gb, "reason": reason})


async def emit_memory_limit_exceeded_async(
    model_id: str, memory_usage_gb: Optional[float], current_usage_gb: Optional[float], limit_gb: Optional[float]
) -> None:
    await _emit(None, UEvent.SYSTEM_ERROR, action="embeddings_memory_limit_exceeded", resource_type="embedding_model", resource_id=model_id, result="failure", metadata={"memory_usage_gb": memory_usage_gb, "current_usage_gb": current_usage_gb, "limit_gb": limit_gb})


async def shutdown_audit_adapter_services() -> None:
    """Shutdown and clear cached UnifiedAuditService instances used by this adapter.

    Ensures pooled connections are closed and background tasks are stopped.
    Safe to call multiple times.
    """
    # Snapshot and clear caches across all known event loops.
    services: list[UnifiedAuditService] = []
    with _STATE_LOCK:
        for state in list(_STATE_BY_LOOP.values()):
            services.extend(list(state.cache.values()))
            state.cache.clear()
            state.services_stopping.clear()

    if not services:
        _stop_sync_loop()
        return

    async def _stop_service(service: UnifiedAuditService) -> None:
        owner_loop = getattr(service, "owner_loop", None)
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if owner_loop and not owner_loop.is_closed() and current_loop is not owner_loop:
            try:
                fut = asyncio.run_coroutine_threadsafe(service.stop(), owner_loop)
                await asyncio.wrap_future(fut)
                return
            except Exception:
                # Fall back to direct stop attempt.
                pass
        try:
            await service.stop()
        except Exception:
            pass

    try:
        await asyncio.gather(*[_stop_service(s) for s in services], return_exceptions=True)
    except Exception:
        # Best-effort shutdown; ignore errors
        pass
    _stop_sync_loop()


# Ensure services are shutdown at interpreter exit to avoid hanging tests
def _shutdown_on_exit() -> None:
    try:
        # Prefer running in a fresh loop if no loop is running
        try:
            loop = asyncio.get_running_loop()
            # Schedule but do not await; at exit there may be no time to run
            try:
                loop.create_task(shutdown_audit_adapter_services())
            except Exception:
                pass
        except RuntimeError:
            try:
                asyncio.run(shutdown_audit_adapter_services())
            except Exception:
                pass
    except Exception:
        pass


atexit.register(_shutdown_on_exit)
