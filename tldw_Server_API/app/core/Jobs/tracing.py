from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any
from loguru import logger


def _enabled() -> bool:
    return str(os.getenv("JOBS_TRACING", "")).lower() in {"1", "true", "yes", "y", "on"}


@contextmanager
def job_span(event: str, *, job: Optional[Dict[str, Any]] = None, attrs: Optional[Dict[str, Any]] = None):
    if not _enabled():
        yield
        return
    ts = time.time()
    meta = {}
    if job:
        for k in ("id", "uuid", "domain", "queue", "job_type"):
            if k in job:
                meta[k] = job.get(k)
    if attrs:
        meta.update(attrs)
    try:
        logger.bind(job_trace=True).info(f"job_span.start event={event} attrs={meta}")
        yield
    except Exception as e:
        logger.bind(job_trace=True).warning(f"job_span.error event={event} attrs={meta} err={e}")
        raise
    finally:
        dur = time.time() - ts
        meta2 = dict(meta)
        meta2["duration_ms"] = int(dur * 1000)
        logger.bind(job_trace=True).info(f"job_span.end event={event} attrs={meta2}")
