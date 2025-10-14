from __future__ import annotations

import asyncio
import os
from typing import Optional
from datetime import datetime

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.metrics import ensure_jobs_metrics_registered, set_queue_gauges


async def run_jobs_metrics_gauges(stop_event: Optional[asyncio.Event] = None) -> None:
    """Periodically report stale processing gauges per domain/queue.

    A stale processing job is status='processing' with an expired lease.
    """
    try:
        from tldw_Server_API.app.core.Jobs.metrics import set_stale_processing
    except Exception:
        logger.debug("Jobs metrics registry unavailable; skipping gauges loop")
        return

    ensure_jobs_metrics_registered()
    jm = JobManager()
    interval = float(os.getenv("JOBS_METRICS_INTERVAL_SEC", "30") or "30")
    ttl_enforce = str(os.getenv("JOBS_TTL_ENFORCE", "")).lower() in {"1","true","yes","y","on"}
    ttl_age = int(os.getenv("JOBS_TTL_AGE_SECONDS", "0") or "0") or None
    ttl_runtime = int(os.getenv("JOBS_TTL_RUNTIME_SECONDS", "0") or "0") or None
    ttl_action = os.getenv("JOBS_TTL_ACTION", "cancel").lower()

    logger.info(f"Starting Jobs metrics gauge loop (every {interval}s)")
    while True:
        try:
            if stop_event and stop_event.is_set():
                logger.info("Stopping Jobs metrics gauge loop on shutdown signal")
                return
            conn = jm._connect()  # use internal helper for a short-lived read
            try:
                if jm.backend == "postgres":
                    with jm._pg_cursor(conn) as cur:
                        # Stale processing counts
                        cur.execute(
                            (
                                "SELECT domain, queue, COUNT(*) as c FROM jobs "
                                "WHERE status='processing' AND (leased_until IS NULL OR leased_until <= NOW()) "
                                "GROUP BY domain, queue"
                            )
                        )
                        rows = cur.fetchall()
                        for r in rows:
                            set_stale_processing(str(r[0]), str(r[1]), int(r[2]))
                        # Queue depth gauges per domain/queue/job_type
                        cur.execute(
                            (
                                "SELECT domain, queue, job_type, "
                                "SUM(CASE WHEN status='queued' AND (available_at IS NULL OR available_at <= NOW()) THEN 1 ELSE 0 END) AS q_ready, "
                                "SUM(CASE WHEN status='queued' AND (available_at IS NOT NULL AND available_at > NOW()) THEN 1 ELSE 0 END) AS q_sched, "
                                "SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS p "
                                "FROM jobs GROUP BY domain, queue, job_type"
                            )
                        )
                        for (domain, queue, job_type, q_ready, q_sched, p) in cur.fetchall():
                            ready = int(q_ready or 0)
                            sched = int(q_sched or 0)
                            set_queue_gauges(str(domain), str(queue), str(job_type), ready, int(p or 0), backlog=(ready + sched), scheduled=sched)
                        # Observe time to expiry for processing jobs
                        try:
                            from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                            reg = get_metrics_registry()
                            cur.execute(
                                "SELECT domain, queue, job_type, leased_until FROM jobs WHERE status='processing' AND leased_until IS NOT NULL"
                            )
                            for (domain, queue, job_type, leased_until) in cur.fetchall():
                                try:
                                    if leased_until is None:
                                        continue
                                    # leased_until from PG comes as datetime
                                    now = datetime.utcnow()
                                    secs = max(0.0, (leased_until - now).total_seconds())
                                    reg.observe("prompt_studio.jobs.time_to_expiry_seconds", secs, {"domain": str(domain), "queue": str(queue), "job_type": str(job_type)})
                                except Exception:
                                    pass
                        except Exception:
                            pass
                else:
                    # Stale processing counts
                    q = (
                        "SELECT domain, queue, COUNT(*) as c FROM jobs "
                        "WHERE status='processing' AND (leased_until IS NULL OR leased_until <= DATETIME('now')) "
                        "GROUP BY domain, queue"
                    )
                    for (domain, queue, c) in conn.execute(q).fetchall():
                        set_stale_processing(str(domain), str(queue), int(c))
                    # Queue depth gauges per domain/queue/job_type
                    q2 = (
                        "SELECT domain, queue, job_type, "
                        "SUM(CASE WHEN status='queued' AND (available_at IS NULL OR available_at <= DATETIME('now')) THEN 1 ELSE 0 END) AS q_ready, "
                        "SUM(CASE WHEN status='queued' AND (available_at IS NOT NULL AND available_at > DATETIME('now')) THEN 1 ELSE 0 END) AS q_sched, "
                        "SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS p "
                        "FROM jobs GROUP BY domain, queue, job_type"
                    )
                    for (domain, queue, job_type, q_ready, q_sched, pd) in conn.execute(q2).fetchall():
                        ready = int(q_ready or 0)
                        sched = int(q_sched or 0)
                        set_queue_gauges(str(domain), str(queue), str(job_type), ready, int(pd or 0), backlog=(ready + sched), scheduled=sched)
                    # Observe time to expiry
                    try:
                        from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                        reg = get_metrics_registry()
                        for (domain, queue, job_type, leased_until) in conn.execute(
                            "SELECT domain, queue, job_type, leased_until FROM jobs WHERE status='processing' AND leased_until IS NOT NULL"
                        ).fetchall():
                            try:
                                if not leased_until:
                                    continue
                                # leased_until stored as TEXT in SQLite
                                from datetime import datetime as _dt
                                lu = _dt.fromisoformat(str(leased_until)) if isinstance(leased_until, str) else leased_until
                                secs = max(0.0, (lu - _dt.utcnow()).total_seconds())
                                reg.observe("prompt_studio.jobs.time_to_expiry_seconds", secs, {"domain": str(domain), "queue": str(queue), "job_type": str(job_type)})
                            except Exception:
                                pass
                    except Exception:
                        pass
                # Apply TTL policies if enabled
                if ttl_enforce and (ttl_age or ttl_runtime):
                    try:
                        jm.apply_ttl_policies(age_seconds=ttl_age, runtime_seconds=ttl_runtime, action=ttl_action)
                    except Exception as _e:
                        logger.debug(f"TTL sweep error: {_e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Jobs metrics gauge loop error: {e}")

        await asyncio.sleep(interval)
