"""
Embeddings audit adapter

Bridges legacy Embeddings audit calls to the unified audit service without
requiring FastAPI dependency injection at call sites. Exposes small, sync-friendly
wrappers that schedule async logging tasks on the running event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
import os
import atexit

from loguru import logger

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    UnifiedAuditService,
    AuditEventType as UEvent,
    AuditContext,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


_service_cache: Dict[str, UnifiedAuditService] = {}
_cache_lock = asyncio.Lock()


def _key_for_user(user_id: Optional[str]) -> str:
    return str(user_id) if user_id is not None else "__default__"


async def _get_service_for_user(user_id: Optional[str]) -> UnifiedAuditService:
    """Get or initialize a cached unified audit service.

    If a numeric user_id is provided, use the per-user audit DB path; otherwise,
    fallback to the default unified audit DB file.
    """
    key = _key_for_user(user_id)
    async with _cache_lock:
        svc = _service_cache.get(key)
        if svc is not None:
            return svc

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
        _service_cache[key] = svc
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
            if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TEST_MODE") or os.getenv("TLDW_TEST_MODE"):
                await svc.flush()
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"Embeddings audit emit failed (ignored): {e}")


def _schedule(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # No running loop; avoid "never awaited" warnings by closing the coroutine.
        try:
            coro.close()  # type: ignore[attr-defined]
        except Exception:
            pass


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
    # Snapshot and clear cache under lock
    async with _cache_lock:
        services = list(_service_cache.values())
        _service_cache.clear()

    if not services:
        return

    try:
        await asyncio.gather(*[s.stop() for s in services], return_exceptions=True)
    except Exception:
        # Best-effort shutdown; ignore errors
        pass


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
