"""
Evaluations audit adapter

Bridges legacy Evaluations audit events to the unified audit service.
Provides small wrappers suitable for use from service code without DI.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    UnifiedAuditService,
    AuditEventType as UEvent,
    AuditContext,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

_svc_cache: Dict[str, UnifiedAuditService] = {}
_lock = asyncio.Lock()


def _key(user_id: Optional[str]) -> str:
    return str(user_id) if user_id is not None else "__default__"


async def _get_svc(user_id: Optional[str]) -> UnifiedAuditService:
    async with _lock:
        key = _key(user_id)
        svc = _svc_cache.get(key)
        if svc is not None:
            return svc
        db_path: Optional[str] = None
        if user_id is not None:
            try:
                db_path = str(DatabasePaths.get_audit_db_path(int(user_id)))
            except Exception:
                db_path = None
        svc = UnifiedAuditService(db_path=db_path)
        await svc.initialize()
        _svc_cache[key] = svc
        return svc


def _schedule(coro) -> None:
    try:
        asyncio.get_running_loop().create_task(coro)
    except RuntimeError:
        pass


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
