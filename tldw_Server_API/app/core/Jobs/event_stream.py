from __future__ import annotations

import os
from typing import Optional, Dict, Any
from loguru import logger


def _events_enabled() -> bool:
    return str(os.getenv("JOBS_EVENTS_ENABLED", "")).lower() in {"1", "true", "yes", "y", "on"}


def emit_job_event(event: str, *, job: Optional[Dict[str, Any]] = None, attrs: Optional[Dict[str, Any]] = None) -> None:
    """Best-effort no-op event emitter.

    If `JOBS_EVENTS_ENABLED=true`, logs a compact event line. In future this can
    be extended to push to an SSE/Webhook bus with rate limiting.
    """
    if not _events_enabled():
        return
    meta = {}
    if job:
        for k in ("id", "uuid", "domain", "queue", "job_type", "status"):
            if k in job:
                meta[k] = job.get(k)
    if attrs:
        meta.update(attrs)
    try:
        logger.bind(job_event=True).info(f"job_event event={event} attrs={meta}")
    except Exception:
        pass

