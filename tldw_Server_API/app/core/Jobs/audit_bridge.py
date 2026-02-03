from __future__ import annotations

import asyncio
import os
import threading
from queue import Empty, Queue
from typing import Any
from uuid import uuid4

from loguru import logger

try:
    from tldw_Server_API.app.core.Audit.unified_audit_service import (
        AuditContext,
        AuditEventCategory,
        AuditEventType,
        AuditSeverity,
        UnifiedAuditService,
    )
except Exception as e:  # pragma: no cover - audit optional
    UnifiedAuditService = None  # type: ignore
    AuditEventCategory = None  # type: ignore
    AuditEventType = None  # type: ignore
    AuditSeverity = None  # type: ignore
    AuditContext = None  # type: ignore
    logger.debug(f"Jobs audit integration unavailable: {e}")


_TRUTHY = {"1", "true", "yes", "y", "on"}

def _audit_enabled() -> bool:
    """Return whether jobs→audit bridge is enabled.

    Evaluated at call time so tests can toggle JOBS_AUDIT_ENABLED after the
    module is imported without requiring a process restart.
    """
    try:
        return (
            UnifiedAuditService is not None
            and str(os.getenv("JOBS_AUDIT_ENABLED", "")).strip().lower() in _TRUTHY
        )
    except Exception:
        return False


def _parse_int_env(name: str, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        value = default
    else:
        try:
            value = int(str(raw).strip())
        except Exception:
            logger.warning(f"Invalid {name}={raw!r}; using default {default}")
            value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def _parse_float_env(name: str, default: float, *, min_value: float | None = None, max_value: float | None = None) -> float:
    raw = os.getenv(name)
    if raw is None:
        value = default
    else:
        try:
            value = float(str(raw).strip())
        except Exception:
            logger.warning(f"Invalid {name}={raw!r}; using default {default}")
            value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value

_EVENT_QUEUE: "Queue[tuple[str, dict[str, Any] | None, dict[str, Any] | None]]" = Queue()
_WORKER_THREAD: threading.Thread | None = None
_WORKER_LOCK = threading.Lock()
_WORKER_READY = threading.Event()
_SHUTDOWN_SENTINEL = ("__shutdown__", None, None)

_AUDIT_EVENT_MAP: dict[str, tuple[AuditEventType, AuditEventCategory, AuditSeverity, str]] = {}
if UnifiedAuditService is not None:
    _AUDIT_EVENT_MAP = {
        "job.created": (AuditEventType.DATA_WRITE, AuditEventCategory.DATA_MODIFICATION, AuditSeverity.INFO, "created"),
        "job.acquired": (AuditEventType.DATA_UPDATE, AuditEventCategory.DATA_MODIFICATION, AuditSeverity.INFO, "acquired"),
        "job.lease_renewed": (AuditEventType.DATA_UPDATE, AuditEventCategory.DATA_MODIFICATION, AuditSeverity.DEBUG, "lease_renewed"),
        "job.completed": (AuditEventType.DATA_UPDATE, AuditEventCategory.DATA_MODIFICATION, AuditSeverity.INFO, "completed"),
        "job.failed": (AuditEventType.DATA_UPDATE, AuditEventCategory.DATA_MODIFICATION, AuditSeverity.WARNING, "failed"),
        "job.cancelled": (AuditEventType.DATA_UPDATE, AuditEventCategory.DATA_MODIFICATION, AuditSeverity.INFO, "cancelled"),
        "job.quarantined": (AuditEventType.SECURITY_VIOLATION, AuditEventCategory.SECURITY, AuditSeverity.WARNING, "quarantined"),
        "job.sla_breached": (AuditEventType.SECURITY_VIOLATION, AuditEventCategory.SECURITY, AuditSeverity.WARNING, "sla_breached"),
    }


def submit_job_audit_event(event: str, *, job: dict[str, Any] | None, attrs: dict[str, Any] | None) -> None:
    """Queue a job lifecycle event for audit logging (best-effort)."""
    if not _audit_enabled():
        return
    if event not in _AUDIT_EVENT_MAP:
        return
    if not _ensure_worker_started():
        return
    try:
        _EVENT_QUEUE.put_nowait((event, job, attrs))
    except Exception as exc:  # pragma: no cover - queue failure unlikely
        logger.debug(f"Jobs audit queue enqueue failed: {exc}")


def shutdown_jobs_audit_bridge() -> None:
    """Signal the audit worker to stop (used in tests/shutdown).

    Safe to call even if audit is disabled - will attempt cleanup regardless.
    """
    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD and _WORKER_THREAD.is_alive():
            try:
                _EVENT_QUEUE.put_nowait(_SHUTDOWN_SENTINEL)
            except Exception:
                pass
            _WORKER_THREAD.join(timeout=5)
        _WORKER_THREAD = None
    # Clear any remaining items in queue
    while True:
        try:
            _EVENT_QUEUE.get_nowait()
        except Empty:
            break


def _ensure_worker_started() -> bool:
    if not _audit_enabled():
        return False
    global _WORKER_THREAD
    with _WORKER_LOCK:
        # If thread exists but is dead, clean it up first
        if _WORKER_THREAD and not _WORKER_THREAD.is_alive():
            _WORKER_THREAD = None
            _WORKER_READY.clear()

        if _WORKER_THREAD and _WORKER_THREAD.is_alive():
            return True

        try:
            # Reset readiness signal before starting
            _WORKER_READY.clear()
            _WORKER_THREAD = threading.Thread(target=_audit_worker_loop, name="jobs-audit-worker", daemon=True)
            _WORKER_THREAD.start()
            # Block briefly until the worker initializes the audit service and schema.
            # This avoids a race where the DB file exists but tables are not yet created,
            # causing tests that probe the file immediately to fail.
            ready = _WORKER_READY.wait(timeout=2.0)
            if not ready:
                # Worker failed to initialize within timeout
                logger.warning("Jobs audit worker failed to initialize within timeout")
                return False
            return True
        except Exception as exc:
            logger.warning(f"Failed to start Jobs audit worker: {exc}")
            _WORKER_THREAD = None
            return False


def _audit_worker_loop() -> None:
    if UnifiedAuditService is None:
        return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    db_path = os.getenv("JOBS_AUDIT_DB_PATH", "Databases/jobs_audit.db")
    retention_days = _parse_int_env("JOBS_AUDIT_RETENTION_DAYS", 30, min_value=1, max_value=3650)
    buffer_size = _parse_int_env("JOBS_AUDIT_BUFFER_SIZE", 100, min_value=1, max_value=100000)
    flush_interval = _parse_float_env("JOBS_AUDIT_FLUSH_SECONDS", 10.0, min_value=0.1, max_value=3600.0)
    service = UnifiedAuditService(
        db_path=db_path,
        retention_days=retention_days,
        enable_pii_detection=False,
        enable_risk_scoring=False,
        buffer_size=buffer_size,
        flush_interval=flush_interval,
    )
    try:
        loop.run_until_complete(service.initialize())
    except Exception as exc:  # pragma: no cover - init failure
        logger.warning(f"Jobs audit worker failed to initialize service: {exc}")
        return
    try:
        _WORKER_READY.set()
    except Exception:
        pass
    try:
        while True:
            try:
                event, job, attrs = _EVENT_QUEUE.get(timeout=0.5)
            except Empty:
                continue
            if (event, job, attrs) == _SHUTDOWN_SENTINEL:
                break
            try:
                loop.run_until_complete(_log_audit_event(service, event, job or {}, attrs or {}))
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning(f"Jobs audit worker failed to log event {event}: {exc}")
    finally:
        try:
            loop.run_until_complete(service.flush())
        except Exception:
            pass
        try:
            loop.run_until_complete(service.stop())
        except Exception:
            pass
        loop.close()


async def _log_audit_event(
    service: UnifiedAuditService,
    event: str,
    job: dict[str, Any],
    attrs: dict[str, Any],
) -> None:
    meta = dict(job)
    meta.update(attrs)
    labels = _AUDIT_EVENT_MAP.get(event)
    if not labels:
        return
    event_type, category, severity, action = labels

    resource_id = None
    if "id" in job:
        resource_id = str(job["id"])
    elif "uuid" in job and job["uuid"]:
        resource_id = str(job["uuid"])

    owner = job.get("owner_user_id")
    request_id = job.get("request_id") or attrs.get("request_id") or str(uuid4())
    context = AuditContext(
        request_id=request_id,
        correlation_id=str(job.get("trace_id") or attrs.get("trace_id") or ""),
        user_id=str(owner) if owner else None,
    )

    # Normalize result to one of: success, failure, error
    result = "success"
    if event == "job.failed":
        result = "failure"
    elif event == "job.sla_breached":
        # Treat SLA breach as a failure for risk scoring and consistency
        result = "failure"

    await service.log_event(
        event_type=event_type,
        category=category,
        severity=severity,
        context=context,
        resource_type="job",
        resource_id=resource_id,
        action=action,
        result=result,
        metadata={
            "domain": job.get("domain"),
            "queue": job.get("queue"),
            "job_type": job.get("job_type"),
            "worker_id": job.get("worker_id"),
            "lease_id": job.get("lease_id"),
            "status": job.get("status"),
            "event": event,
            **{k: v for k, v in attrs.items() if k not in {"request_id", "trace_id"}},
        },
    )
    # Flush aggressively while the worker thread owns the loop to avoid leaving buffered events.
    await service.flush()


__all__ = ["submit_job_audit_event", "shutdown_jobs_audit_bridge"]
