from __future__ import annotations

import os
import time
import json
from typing import Optional, Dict, Any
from loguru import logger

from .audit_bridge import submit_job_audit_event


def _events_enabled() -> bool:
    return str(os.getenv("JOBS_EVENTS_ENABLED", "")).lower() in {"1", "true", "yes", "y", "on"}


def emit_job_event(event: str, *, job: Optional[Dict[str, Any]] = None, attrs: Optional[Dict[str, Any]] = None) -> None:
    """Best-effort no-op event emitter.

    If `JOBS_EVENTS_ENABLED=true`, logs a compact event line. In future this can
    be extended to push to an SSE/Webhook bus with rate limiting.
    """
    try:
        submit_job_audit_event(event, job=job, attrs=attrs)
    except Exception:
        # Audit integration is best-effort. Errors should never break job flow.
        pass
    # Only skip entirely when neither logging nor outbox are enabled
    if not (_events_enabled() or str(os.getenv("JOBS_EVENTS_OUTBOX", "")).lower() in {"1","true","yes","y","on"}):
        return
    meta = {}
    if job:
        for k in ("id", "uuid", "domain", "queue", "job_type", "status"):
            if k in job:
                meta[k] = job.get(k)
    if attrs:
        meta.update(attrs)
    if _events_enabled():
        try:
            logger.bind(job_event=True).info(f"job_event event={event} attrs={meta}")
        except Exception:
            pass
    # Outbox write (append-only) when enabled
    # Optional soft rate-limit for extremely high churn
    try:
        if _events_enabled() or str(os.getenv("JOBS_EVENTS_OUTBOX", "")).lower() in {"1","true","yes","y","on"}:
            # Basic rate limiter: drop writes if exceeding JOBS_EVENTS_RATE_LIMIT_HZ
            try:
                hz = float(os.getenv("JOBS_EVENTS_RATE_LIMIT_HZ", "0") or "0")
            except Exception:
                hz = 0.0
            if hz > 0:
                now = time.time()
                last = _rate_state.get("last_ts", 0.0)
                min_interval = 1.0 / max(0.0001, hz)
                # Always allow admin sweep/maintenance events
                is_admin_ev = event.startswith("jobs.")
                if not is_admin_ev and (now - last) < min_interval:
                    return
                _rate_state["last_ts"] = now
            from tldw_Server_API.app.core.Jobs.manager import JobManager
            # Admin context for outbox writes (RLS bypass)
            try:
                JobManager.set_rls_context(is_admin=True, domain_allowlist=None, owner_user_id=None)
            except Exception:
                pass
            jm = JobManager()
            conn = jm._connect()
            try:
                if jm.backend == "postgres":
                    with jm._pg_cursor(conn) as cur:
                        cur.execute(
                            (
                                "INSERT INTO job_events(job_id, domain, queue, job_type, event_type, attrs_json, owner_user_id, request_id, trace_id, created_at) "
                                "VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, NOW())"
                            ),
                            (
                                (job or {}).get("id"),
                                (job or {}).get("domain"),
                                (job or {}).get("queue"),
                                (job or {}).get("job_type"),
                                event,
                                json.dumps(attrs or {}),
                                (job or {}).get("owner_user_id"),
                                (job or {}).get("request_id"),
                                (job or {}).get("trace_id"),
                            ),
                        )
                        conn.commit()
                else:
                    conn.execute(
                        (
                            "INSERT INTO job_events(job_id, domain, queue, job_type, event_type, attrs_json, owner_user_id, request_id, trace_id, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, DATETIME('now'))"
                        ),
                        (
                            (job or {}).get("id"),
                            (job or {}).get("domain"),
                            (job or {}).get("queue"),
                            (job or {}).get("job_type"),
                            event,
                            json.dumps(attrs or {}),
                            (job or {}).get("owner_user_id"),
                            (job or {}).get("request_id"),
                            (job or {}).get("trace_id"),
                        ),
                    )
                    conn.commit()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
                try:
                    JobManager.clear_rls_context()
                except Exception:
                    pass
    except Exception:
        # Swallow outbox errors; logging already occurred
        pass

# Module-level state for soft rate limiter
_rate_state: Dict[str, float] = {}
