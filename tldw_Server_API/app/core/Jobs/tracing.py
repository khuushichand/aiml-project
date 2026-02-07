from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any

from loguru import logger
from tldw_Server_API.app.core.testing import is_truthy


def _enabled() -> bool:
    return is_truthy(os.getenv("JOBS_TRACING"))


@contextmanager
def job_span(event: str, *, job: dict[str, Any] | None = None, attrs: dict[str, Any] | None = None):
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
