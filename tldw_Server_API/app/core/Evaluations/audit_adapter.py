"""
Evaluations audit adapter

Bridges legacy Evaluations audit events to the unified audit service.
Provides small wrappers suitable for use from service code without DI.
"""

from __future__ import annotations

import asyncio
import atexit
import os
import threading
import weakref
import warnings
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    UnifiedAuditService,
    AuditEventType as UEvent,
    AuditContext,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

# LRU cache for audit services with configurable max size
_MAX_CACHED_SERVICES = int(os.getenv("EVALUATIONS_AUDIT_MAX_CACHED_SERVICES", "20"))


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
    loop = asyncio.get_running_loop()
    with _STATE_LOCK:
        state = _STATE_BY_LOOP.get(loop)
        if state is None:
            state = _LoopState()
            _STATE_BY_LOOP[loop] = state
        return state


def _key(user_id: Optional[str]) -> str:
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
            name="evaluations-audit-sync-loop",
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


async def _get_svc(user_id: Optional[str]) -> UnifiedAuditService:
    """Get or initialize a cached unified audit service with LRU eviction."""
    key = _key(user_id)
    state = _state_for_loop()
    async with state.lock:
        # Check if this key is being stopped
        if key in state.services_stopping:
            pass  # Will create new one
        elif key in state.cache:
            # Move to end (most recently used)
            state.cache.move_to_end(key)
            return state.cache[key]

        # Evict oldest if at capacity
        while len(state.cache) >= _MAX_CACHED_SERVICES:
            await _evict_oldest_service(state)

        db_path: Optional[str] = None
        if user_id is not None:
            try:
                db_path = str(DatabasePaths.get_audit_db_path(int(user_id)))
            except Exception:
                db_path = None
        svc = UnifiedAuditService(db_path=db_path)
        await svc.initialize()
        state.cache[key] = svc
        return svc


def _schedule(coro) -> None:
    try:
        asyncio.get_running_loop().create_task(coro)
        return
    except RuntimeError:
        pass

    loop = _ensure_sync_loop()
    if loop is None:
        # No loop available; suppress warning and close coroutine
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
                logger.warning(f"Evaluations audit sync task failed: {exc}")
        except Exception:
            pass

    fut.add_done_callback(_log_failure)
    if _in_test_mode():
        try:
            fut.result(timeout=5)
        except Exception as e:
            logger.warning(f"Evaluations audit sync task timed out: {e}")


async def _emit(
    *,
    user_id: Optional[str],
    event_type: UEvent,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    result: str = "success",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        svc = await _get_svc(user_id)
        ctx = AuditContext(user_id=user_id)
        await svc.log_event(
            event_type=event_type,
            context=ctx,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            metadata=metadata,
        )
        # Flush immediately in test environments to make events visible to queries
        try:
            if _in_test_mode():
                await svc.flush()
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"Evaluations audit emit failed: {e}")


# Convenience wrappers

def log_evaluation_created(*, user_id: str, eval_id: str, name: str, eval_type: str) -> None:
    _schedule(_emit(user_id=user_id, event_type=UEvent.DATA_WRITE, action="evaluation_create", resource_type="evaluation", resource_id=eval_id, metadata={"name": name, "type": eval_type}))


def log_evaluation_updated(*, user_id: str, eval_id: str, updates: Dict[str, Any]) -> None:
    _schedule(_emit(user_id=user_id, event_type=UEvent.DATA_UPDATE, action="evaluation_update", resource_type="evaluation", resource_id=eval_id, metadata={"updates": list(updates.keys())}))


def log_evaluation_deleted(*, user_id: str, eval_id: str) -> None:
    _schedule(_emit(user_id=user_id, event_type=UEvent.DATA_DELETE, action="evaluation_delete", resource_type="evaluation", resource_id=eval_id))


def log_run_started(*, user_id: str, run_id: str, eval_id: str, target_model: str) -> None:
    _schedule(_emit(user_id=user_id, event_type=UEvent.EVAL_STARTED, action="run_create", resource_type="evaluation_run", resource_id=run_id, metadata={"eval_id": eval_id, "target_model": target_model}))


def log_run_cancelled(*, user_id: str, run_id: str) -> None:
    _schedule(_emit(user_id=user_id, event_type=UEvent.EVAL_FAILED, action="run_cancelled", resource_type="evaluation_run", resource_id=run_id, result="failure"))


def log_dataset_created(*, user_id: str, dataset_id: str, name: str, samples: int) -> None:
    _schedule(_emit(user_id=user_id, event_type=UEvent.DATA_WRITE, action="dataset_create", resource_type="dataset", resource_id=dataset_id, metadata={"name": name, "samples": samples}))


def log_dataset_deleted(*, user_id: str, dataset_id: str) -> None:
    _schedule(_emit(user_id=user_id, event_type=UEvent.DATA_DELETE, action="dataset_delete", resource_type="dataset", resource_id=dataset_id))


def log_webhook_registration(*, user_id: str, webhook_id: Optional[str], url: str, events: list[str], success: bool, error: Optional[str] = None) -> None:
    event = UEvent.SECURITY_SCAN if success else UEvent.SECURITY_VIOLATION
    res = "success" if success else "failure"
    _schedule(_emit(user_id=user_id, event_type=event, action="webhook_register", resource_type="webhook", resource_id=str(webhook_id) if webhook_id else None, result=res, metadata={"url": url, "events": events, "error": error}))


def log_webhook_unregistration(*, user_id: str, webhook_id: Optional[str], url: str, events: list[str], success: bool, error: Optional[str] = None) -> None:
    event = UEvent.SECURITY_SCAN if success else UEvent.SECURITY_VIOLATION
    res = "success" if success else "failure"
    _schedule(_emit(user_id=user_id, event_type=event, action="webhook_unregister", resource_type="webhook", resource_id=str(webhook_id) if webhook_id else None, result=res, metadata={"url": url, "events": events, "error": error}))


async def shutdown_evaluations_audit_services() -> None:
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


def _shutdown_on_exit() -> None:
    """Atexit handler to ensure services are shutdown at interpreter exit."""
    try:
        try:
            loop = asyncio.get_running_loop()
            try:
                loop.create_task(shutdown_evaluations_audit_services())
            except Exception:
                pass
        except RuntimeError:
            try:
                asyncio.run(shutdown_evaluations_audit_services())
            except Exception:
                pass
    except Exception:
        pass


atexit.register(_shutdown_on_exit)
