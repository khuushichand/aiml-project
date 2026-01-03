from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
import os

from loguru import logger


_DEFAULT_BUFFER_SIZE = 2000
_BUFFER_SIZE = max(100, int(os.getenv("SYSTEM_LOG_BUFFER_SIZE", str(_DEFAULT_BUFFER_SIZE))))
_BUFFER: deque[Dict[str, Any]] = deque(maxlen=_BUFFER_SIZE)
_BUFFER_LOCK = Lock()
_SINK_ID: Optional[int] = None

_EXTRA_FIELDS = {
    "request_id",
    "org_id",
    "user_id",
    "trace_id",
    "span_id",
    "correlation_id",
    "event",
}


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_extra(extra: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key in _EXTRA_FIELDS:
        if key not in extra:
            continue
        val = extra.get(key)
        if key in {"org_id", "user_id"}:
            payload[key] = _coerce_optional_int(val)
        else:
            payload[key] = val if val is not None else None
    return payload


def _log_sink(message: Any) -> None:
    record = message.record
    extra = _extract_extra(record.get("extra", {}))
    entry = {
        "timestamp": record.get("time"),
        "level": record.get("level").name if record.get("level") else None,
        "message": record.get("message"),
        "logger": record.get("name"),
        "module": record.get("module"),
        "function": record.get("function"),
        "line": record.get("line"),
        **extra,
    }
    with _BUFFER_LOCK:
        _BUFFER.append(entry)


def _sink_still_present(sink_id: int) -> bool:
    # Loguru doesn't expose a public API for checking removed sinks.
    try:
        core = getattr(logger, "_core", None)
        handlers = getattr(core, "handlers", None)
        return isinstance(handlers, dict) and sink_id in handlers
    except (AttributeError, TypeError, KeyError):
        return False


def ensure_system_log_buffer() -> None:
    """Attach a Loguru sink to capture recent logs into an in-memory ring buffer."""
    global _SINK_ID
    if _SINK_ID is not None and _sink_still_present(_SINK_ID):
        return
    _SINK_ID = logger.add(
        _log_sink,
        level=os.getenv("SYSTEM_LOG_LEVEL", "DEBUG"),
        backtrace=False,
        diagnose=False,
        enqueue=False,
    )


def query_system_logs(
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    level: Optional[str] = None,
    service: Optional[str] = None,
    query: Optional[str] = None,
    org_id: Optional[int] = None,
    org_ids: Optional[List[int]] = None,
    user_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    ensure_system_log_buffer()
    level_norm = level.strip().upper() if level else None
    service_norm = service.strip().lower() if service else None
    query_norm = query.strip().lower() if query else None

    with _BUFFER_LOCK:
        entries = list(_BUFFER)

    filtered: List[Dict[str, Any]] = []
    org_id_set = {org_id} if org_id is not None else set(org_ids or [])
    for entry in entries:
        timestamp = entry.get("timestamp")
        if isinstance(timestamp, datetime):
            if start and timestamp < start:
                continue
            if end and timestamp > end:
                continue
        if level_norm and (entry.get("level") or "").upper() != level_norm:
            continue
        if service_norm:
            logger_name = (entry.get("logger") or "").lower()
            module_name = (entry.get("module") or "").lower()
            if service_norm not in logger_name and service_norm not in module_name:
                continue
        if query_norm and query_norm not in (entry.get("message") or "").lower():
            continue
        if org_id_set:
            if entry.get("org_id") not in org_id_set:
                continue
        if user_id is not None and entry.get("user_id") != user_id:
            continue
        filtered.append(entry)

    filtered.sort(key=lambda item: item.get("timestamp") or datetime.min, reverse=True)
    total = len(filtered)
    safe_offset = max(0, offset)
    safe_limit = max(1, limit)
    return filtered[safe_offset:safe_offset + safe_limit], total
