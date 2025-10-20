from __future__ import annotations

"""
Jobs Metrics Service

Periodic reconcile of job_counters and gauges with group caps to avoid heavy scans.

This service is intentionally light-weight and opt-in via environment flags.

Env vars:
  - JOBS_METRICS_RECONCILE_ENABLE: truthy to enable service loop (off by default)
  - JOBS_METRICS_RECONCILE_INTERVAL_SEC: sleep interval between passes (default 10)
  - JOBS_METRICS_RECONCILE_GROUPS_PER_TICK: max distinct (domain,queue,job_type)
    groups to reconcile per pass (default 100)

Usage:
  from tldw_Server_API.app.services.jobs_metrics_service import JobsMetricsService
  svc = JobsMetricsService(); await svc.run()  # or call reconcile_once() manually

Tests can call reconcile_once(limit) directly for determinism.
"""

import os
import time
from typing import List, Tuple, Optional

from loguru import logger

try:
    # JobManager path in this repository
    from tldw_Server_API.app.core.Jobs.manager import JobManager
except Exception:  # Fallback path for historical imports
    from tldw_Server_API.app.core.Jobs.manager import JobManager  # type: ignore


def _is_truthy(v: Optional[str]) -> bool:
    return str(v or "").lower() in {"1", "true", "yes", "y", "on"}


class JobsMetricsService:
    def __init__(self) -> None:
        self.interval = float(os.getenv("JOBS_METRICS_RECONCILE_INTERVAL_SEC", "10") or "10")
        self.group_cap = int(os.getenv("JOBS_METRICS_RECONCILE_GROUPS_PER_TICK", "100") or "100")
        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        self.jm = JobManager(backend=backend, db_url=db_url)

    def reconcile_once(self, *, limit_groups: Optional[int] = None) -> int:
        """Recompute job_counters for up to limit_groups groups.

        Strategy:
          - Select distinct (domain,queue,job_type) from jobs, left join job_counters
            to get last updated_at when available.
          - Order by counters.updated_at ASC NULLS FIRST to prioritize stale/missing rows.
          - Limit by `limit_groups` (defaults to configured cap).
          - For each group: compute queued-ready, queued-scheduled, processing counts
            and upsert into job_counters, then refresh gauges best-effort.

        Returns number of groups reconciled.
        """
        cap = int(limit_groups if limit_groups is not None else self.group_cap)
        if cap <= 0:
            return 0
        jm = self.jm
        conn = jm._connect()
        reconciled = 0
        try:
            if jm.backend == "postgres":
                with jm._pg_cursor(conn) as cur:
                    cur.execute(
                        (
                            "SELECT j.domain, j.queue, j.job_type, c.updated_at AS cnt_updated "
                            "FROM (SELECT DISTINCT domain, queue, job_type FROM jobs) j "
                            "LEFT JOIN job_counters c ON (c.domain=j.domain AND c.queue=j.queue AND c.job_type=j.job_type) "
                            "ORDER BY c.updated_at ASC NULLS FIRST, j.domain, j.queue, j.job_type LIMIT %s"
                        ),
                        (cap,),
                    )
                    groups = cur.fetchall() or []
                    for g in groups:
                        d = g["domain"] if isinstance(g, dict) else g[0]
                        q = g["queue"] if isinstance(g, dict) else g[1]
                        jt = g["job_type"] if isinstance(g, dict) else g[2]
                        # Compute counts
                        cur.execute(
                            "SELECT COUNT(*) c FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='queued' AND (available_at IS NULL OR available_at <= NOW())",
                            (d, q, jt),
                        )
                        r_ready = int(cur.fetchone()[0])
                        cur.execute(
                            "SELECT COUNT(*) c FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='queued' AND (available_at IS NOT NULL AND available_at > NOW())",
                            (d, q, jt),
                        )
                        r_sched = int(cur.fetchone()[0])
                        cur.execute(
                            "SELECT COUNT(*) c FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='processing'",
                            (d, q, jt),
                        )
                        r_proc = int(cur.fetchone()[0])
                        # Upsert counters
                        cur.execute(
                            (
                                "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count,updated_at) "
                                "VALUES(%s,%s,%s,%s,%s,%s,0,NOW()) "
                                "ON CONFLICT(domain,queue,job_type) DO UPDATE SET ready_count=EXCLUDED.ready_count, scheduled_count=EXCLUDED.scheduled_count, processing_count=EXCLUDED.processing_count, updated_at=NOW()"
                            ),
                            (d, q, jt, int(r_ready), int(r_sched), int(r_proc)),
                        )
                        try:
                            jm._update_gauges(domain=d, queue=q, job_type=jt)
                        except Exception:
                            pass
                        reconciled += 1
            else:
                # SQLite
                groups = conn.execute(
                    (
                        "SELECT j.domain, j.queue, j.job_type, c.updated_at AS cnt_updated "
                        "FROM (SELECT DISTINCT domain, queue, job_type FROM jobs) j "
                        "LEFT JOIN job_counters c ON (c.domain=j.domain AND c.queue=j.queue AND c.job_type=j.job_type) "
                        "ORDER BY c.updated_at ASC, j.domain, j.queue, j.job_type LIMIT ?"
                    ),
                    (cap,),
                ).fetchall() or []
                for d, q, jt, _ in groups:
                    q_ready = int(
                        conn.execute(
                            "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND job_type=? AND status='queued' AND (available_at IS NULL OR available_at <= DATETIME('now'))",
                            (d, q, jt),
                        ).fetchone()[0]
                    )
                    q_sched = int(
                        conn.execute(
                            "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND job_type=? AND status='queued' AND (available_at IS NOT NULL AND available_at > DATETIME('now'))",
                            (d, q, jt),
                        ).fetchone()[0]
                    )
                    p = int(
                        conn.execute(
                            "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND job_type=? AND status='processing'",
                            (d, q, jt),
                        ).fetchone()[0]
                    )
                    conn.execute(
                        (
                            "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count,updated_at) VALUES(?,?,?,?,?,?,0, DATETIME('now')) "
                            "ON CONFLICT(domain,queue,job_type) DO UPDATE SET ready_count=excluded.ready_count, scheduled_count=excluded.scheduled_count, processing_count=excluded.processing_count, updated_at=DATETIME('now')"
                        ),
                        (d, q, jt, int(q_ready), int(q_sched), int(p)),
                    )
                    try:
                        self.jm._update_gauges(domain=d, queue=q, job_type=jt)
                    except Exception:
                        pass
                    reconciled += 1
                try:
                    conn.commit()
                except Exception:
                    pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return reconciled

    def run_forever(self) -> None:
        """Blocking loop for environments that prefer threads/processes over asyncio."""
        if not _is_truthy(os.getenv("JOBS_METRICS_RECONCILE_ENABLE")):
            logger.debug("Jobs metrics reconcile service disabled")
            return
        logger.info("Jobs metrics reconcile service started")
        while True:
            try:
                n = self.reconcile_once()
                logger.debug(f"Jobs metrics reconcile tick: updated {n} group(s)")
            except Exception as e:
                logger.warning(f"Jobs metrics reconcile error: {e}")
            time.sleep(self.interval)


# --- Async wrappers compatible with app/main startup expectations ---
async def run_jobs_metrics_reconcile(stop_event) -> None:
    """Async reconcile loop that respects a stop_event (asyncio.Event)."""
    if not _is_truthy(os.getenv("JOBS_METRICS_RECONCILE_ENABLE")):
        return
    svc = JobsMetricsService()
    interval = svc.interval
    import asyncio
    while not stop_event.is_set():
        try:
            svc.reconcile_once()
        except Exception as e:
            logger.debug(f"Jobs reconcile loop error: {e}")
        await asyncio.sleep(interval)


async def run_jobs_metrics_gauges(stop_event) -> None:
    """Compute SLO percentile gauges for queue latency and duration per owner.

    Controlled by env:
      - JOBS_SLO_ENABLE: truthy to enable (default false)
      - JOBS_SLO_WINDOW_HOURS: window to consider (default 24)
      - JOBS_METRICS_INTERVAL_SEC: interval between computations (default 5)
      - JOBS_SLO_MAX_GROUPS: max owner groups per window (default 100)
    """
    import asyncio
    if not _is_truthy(os.getenv("JOBS_SLO_ENABLE")):
        return
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
    except Exception:
        return
    reg = get_metrics_registry()
    if not reg:
        return
    db_url = os.getenv("JOBS_DB_URL")
    backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
    jm = JobManager(backend=backend, db_url=db_url)
    try:
        interval = float(os.getenv("JOBS_METRICS_INTERVAL_SEC", "5") or "5")
    except Exception:
        interval = 5.0
    try:
        window_h = int(os.getenv("JOBS_SLO_WINDOW_HOURS", "24") or "24")
    except Exception:
        window_h = 24
    try:
        max_groups = int(os.getenv("JOBS_SLO_MAX_GROUPS", "100") or "100")
    except Exception:
        max_groups = 100

    def _set_gauges(d: str, q: str, jt: str, owner: str, qlat_p: Tuple[float,float,float], dur_p: Tuple[float,float,float]):
        labels = {"domain": d, "queue": q, "job_type": jt or "", "owner_user_id": owner or ""}
        reg.set_gauge("jobs.queue_latency_p50_seconds", float(qlat_p[0]), labels)
        reg.set_gauge("jobs.queue_latency_p90_seconds", float(qlat_p[1]), labels)
        reg.set_gauge("jobs.queue_latency_p99_seconds", float(qlat_p[2]), labels)
        reg.set_gauge("jobs.duration_p50_seconds", float(dur_p[0]), labels)
        reg.set_gauge("jobs.duration_p90_seconds", float(dur_p[1]), labels)
        reg.set_gauge("jobs.duration_p99_seconds", float(dur_p[2]), labels)

    def _percentiles(values: List[float]) -> Tuple[float, float, float]:
        if not values:
            return (0.0, 0.0, 0.0)
        vs = sorted(values)
        def p(x: float) -> float:
            if not vs:
                return 0.0
            idx = max(0, min(len(vs) - 1, int((x / 100.0) * (len(vs) - 1))))
            return float(vs[idx])
        return (p(50.0), p(90.0), p(99.0))

    while not stop_event.is_set():
        try:
            conn = jm._connect()
            try:
                rows = []
                if jm.backend == "postgres":
                    with jm._pg_cursor(conn) as cur:
                        cur.execute(
                            (
                                "SELECT owner_user_id, domain, queue, job_type, "
                                "EXTRACT(EPOCH FROM (acquired_at - created_at)) AS qlat, "
                                "EXTRACT(EPOCH FROM (completed_at - COALESCE(started_at, acquired_at))) AS dur "
                                "FROM jobs WHERE status='completed' AND completed_at >= (NOW() - (%s || ' hours')::interval)"
                            ),
                            (int(window_h),),
                        )
                        rows = cur.fetchall() or []
                else:
                    rows = conn.execute(
                        (
                            "SELECT owner_user_id, domain, queue, job_type, "
                            "(strftime('%s', acquired_at) - strftime('%s', created_at)) AS qlat, "
                            "(strftime('%s', completed_at) - strftime('%s', COALESCE(started_at, acquired_at))) AS dur "
                            "FROM jobs WHERE status='completed' AND completed_at >= DATETIME('now', ?)"
                        ),
                        (f"-{int(window_h)} hours",),
                    ).fetchall() or []
                # Group by (owner, domain, queue, job_type)
                from collections import defaultdict
                grp = defaultdict(lambda: {"qlat": [], "dur": []})
                for r in rows:
                    owner = r[0] if not isinstance(r, dict) else r.get("owner_user_id")
                    d = r[1] if not isinstance(r, dict) else r.get("domain")
                    q = r[2] if not isinstance(r, dict) else r.get("queue")
                    jt = r[3] if not isinstance(r, dict) else r.get("job_type")
                    qlat = r[4] if not isinstance(r, dict) else r.get("qlat")
                    dur = r[5] if not isinstance(r, dict) else r.get("dur")
                    try:
                        if qlat is not None:
                            grp[(str(owner or ""), str(d or ""), str(q or ""), str(jt or ""))]["qlat"].append(float(qlat))
                        if dur is not None:
                            grp[(str(owner or ""), str(d or ""), str(q or ""), str(jt or ""))]["dur"].append(float(dur))
                    except Exception:
                        continue
                # Limit groups per loop
                count = 0
                for (owner, d, q, jt), vals in grp.items():
                    _set_gauges(d, q, jt, owner, _percentiles(vals["qlat"]), _percentiles(vals["dur"]))
                    count += 1
                    if count >= max_groups:
                        break
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Jobs SLO gauges loop error: {e}")
        await asyncio.sleep(interval)
