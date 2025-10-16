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
    # Register audio-specific metrics lazily
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry, MetricDefinition, MetricType
        reg = get_metrics_registry()
        try:
            reg.register_metric(MetricDefinition(
                name="audio.jobs.by_owner_status",
                type=MetricType.GAUGE,
                description="Audio jobs count by owner and status",
                labels=["owner_user_id", "status"],
            ))
        except Exception:
            pass
    except Exception:
        pass
    jm = JobManager()
    interval = float(os.getenv("JOBS_METRICS_INTERVAL_SEC", "30") or "30")
    slo_enabled = str(os.getenv("JOBS_SLO_ENABLE", "")).lower() in {"1","true","yes","y","on"}
    slo_window_h = int(os.getenv("JOBS_SLO_WINDOW_HOURS", "6") or "6")
    slo_max_groups = int(os.getenv("JOBS_SLO_MAX_GROUPS", "100") or "100")
    ttl_enforce = str(os.getenv("JOBS_TTL_ENFORCE", "")).lower() in {"1","true","yes","y","on"}
    ttl_age = int(os.getenv("JOBS_TTL_AGE_SECONDS", "0") or "0") or None
    ttl_runtime = int(os.getenv("JOBS_TTL_RUNTIME_SECONDS", "0") or "0") or None
    ttl_action = os.getenv("JOBS_TTL_ACTION", "cancel").lower()
    # Prune/retention
    prune_enforce = str(os.getenv("JOBS_PRUNE_ENFORCE", "")).lower() in {"1","true","yes","y","on"}
    retention_terminal_days = int(os.getenv("JOBS_RETENTION_DAYS_TERMINAL", "0") or "0")
    retention_nonterminal_days = int(os.getenv("JOBS_RETENTION_DAYS_NONTERMINAL", "0") or "0")

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
                        # Optional reconciliation into job_counters
                        try:
                            if str(os.getenv("JOBS_COUNTERS_RECONCILE", "")).lower() in {"1","true","yes","y","on"}:
                                cur.execute(
                                    (
                                        "SELECT domain, queue, job_type, "
                                        "SUM(CASE WHEN status='queued' AND (available_at IS NULL OR available_at <= NOW()) THEN 1 ELSE 0 END) AS q_ready, "
                                        "SUM(CASE WHEN status='queued' AND (available_at IS NOT NULL AND available_at > NOW()) THEN 1 ELSE 0 END) AS q_sched, "
                                        "SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS p, "
                                        "SUM(CASE WHEN status='quarantined' THEN 1 ELSE 0 END) AS qz "
                                        "FROM jobs GROUP BY domain, queue, job_type"
                                    )
                                )
                                rowsr = cur.fetchall() or []
                                for (d, q, jt, rdy, sch, proc, qz) in rowsr:
                                    try:
                                        cur.execute(
                                            (
                                                "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                                                "ON CONFLICT (domain,queue,job_type) DO UPDATE SET ready_count = EXCLUDED.ready_count, scheduled_count = EXCLUDED.scheduled_count, processing_count = EXCLUDED.processing_count, quarantined_count = EXCLUDED.quarantined_count, updated_at = NOW()"
                                            ),
                                            (str(d), str(q), str(jt), int(rdy or 0), int(sch or 0), int(proc or 0), int(qz or 0)),
                                        )
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        # Audio jobs by owner/status
                        try:
                            cur.execute(
                                "SELECT owner_user_id, status, COUNT(*) FROM jobs WHERE domain=%s GROUP BY owner_user_id, status",
                                ("audio",),
                            )
                            rows = cur.fetchall() or []
                            try:
                                reg = get_metrics_registry()
                                for (owner_user_id, status, count) in rows:
                                    reg.set_gauge("audio.jobs.by_owner_status", int(count or 0), {"owner_user_id": str(owner_user_id or ""), "status": str(status or "")})
                            except Exception:
                                pass
                        except Exception:
                            pass
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
                        # SLO percentiles per owner/job_type (windowed)
                        if slo_enabled:
                            try:
                                # Queue latency percentiles (limit groups when many owners)
                                if slo_max_groups and slo_max_groups > 0:
                                    cur.execute(
                                        (
                                            "WITH groups AS ("
                                            "  SELECT domain, queue, job_type, owner_user_id, COUNT(*) AS c "
                                            "  FROM jobs WHERE acquired_at IS NOT NULL AND created_at >= NOW() - (%s || ' hours')::interval "
                                            "  GROUP BY domain, queue, job_type, owner_user_id "
                                            "  ORDER BY c DESC LIMIT %s"
                                            ") "
                                            "SELECT j.domain, j.queue, j.job_type, j.owner_user_id, "
                                            "percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (acquired_at - created_at))) AS p50, "
                                            "percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (acquired_at - created_at))) AS p90, "
                                            "percentile_cont(0.99) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (acquired_at - created_at))) AS p99 "
                                            "FROM jobs j JOIN groups g USING (domain, queue, job_type, owner_user_id) "
                                            "WHERE j.acquired_at IS NOT NULL AND j.created_at >= NOW() - (%s || ' hours')::interval "
                                            "GROUP BY j.domain, j.queue, j.job_type, j.owner_user_id"
                                        ),
                                        (int(slo_window_h), int(slo_max_groups), int(slo_window_h)),
                                    )
                                else:
                                    cur.execute(
                                        (
                                            "SELECT domain, queue, job_type, owner_user_id, "
                                            "percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (acquired_at - created_at))) AS p50, "
                                            "percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (acquired_at - created_at))) AS p90, "
                                            "percentile_cont(0.99) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (acquired_at - created_at))) AS p99 "
                                            "FROM jobs WHERE acquired_at IS NOT NULL AND created_at >= NOW() - (%s || ' hours')::interval "
                                            "GROUP BY domain, queue, job_type, owner_user_id"
                                        ),
                                        (int(slo_window_h),),
                                    )
                                rows = cur.fetchall() or []
                                from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                                reg = get_metrics_registry()
                                for (domain, queue, job_type, owner, p50, p90, p99) in rows:
                                    labels = {"domain": str(domain), "queue": str(queue), "job_type": str(job_type), "owner_user_id": str(owner or "")}
                                    if p50 is not None:
                                        reg.set_gauge("prompt_studio.jobs.queue_latency_p50_seconds", float(p50), labels)
                                    if p90 is not None:
                                        reg.set_gauge("prompt_studio.jobs.queue_latency_p90_seconds", float(p90), labels)
                                    if p99 is not None:
                                        reg.set_gauge("prompt_studio.jobs.queue_latency_p99_seconds", float(p99), labels)
                            except Exception:
                                pass
                            try:
                                # Duration percentiles (completed runs) with optional group limiting
                                if slo_max_groups and slo_max_groups > 0:
                                    cur.execute(
                                        (
                                            "WITH groups AS ("
                                            "  SELECT domain, queue, job_type, owner_user_id, COUNT(*) AS c "
                                            "  FROM jobs WHERE completed_at IS NOT NULL AND created_at >= NOW() - (%s || ' hours')::interval "
                                            "  GROUP BY domain, queue, job_type, owner_user_id "
                                            "  ORDER BY c DESC LIMIT %s"
                                            ") "
                                            "SELECT j.domain, j.queue, j.job_type, j.owner_user_id, "
                                            "percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - COALESCE(started_at, acquired_at)))) AS p50, "
                                            "percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - COALESCE(started_at, acquired_at)))) AS p90, "
                                            "percentile_cont(0.99) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - COALESCE(started_at, acquired_at)))) AS p99 "
                                            "FROM jobs j JOIN groups g USING (domain, queue, job_type, owner_user_id) "
                                            "WHERE j.completed_at IS NOT NULL AND j.created_at >= NOW() - (%s || ' hours')::interval "
                                            "GROUP BY j.domain, j.queue, j.job_type, j.owner_user_id"
                                        ),
                                        (int(slo_window_h), int(slo_max_groups), int(slo_window_h)),
                                    )
                                else:
                                    cur.execute(
                                        (
                                            "SELECT domain, queue, job_type, owner_user_id, "
                                            "percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - COALESCE(started_at, acquired_at)))) AS p50, "
                                            "percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - COALESCE(started_at, acquired_at)))) AS p90, "
                                            "percentile_cont(0.99) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - COALESCE(started_at, acquired_at)))) AS p99 "
                                            "FROM jobs WHERE completed_at IS NOT NULL AND created_at >= NOW() - (%s || ' hours')::interval "
                                            "GROUP BY domain, queue, job_type, owner_user_id"
                                        ),
                                        (int(slo_window_h),),
                                    )
                                rows2 = cur.fetchall() or []
                                from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                                reg2 = get_metrics_registry()
                                for (domain, queue, job_type, owner, p50, p90, p99) in rows2:
                                    labels = {"domain": str(domain), "queue": str(queue), "job_type": str(job_type), "owner_user_id": str(owner or "")}
                                    if p50 is not None:
                                        reg2.set_gauge("prompt_studio.jobs.duration_p50_seconds", float(p50), labels)
                                    if p90 is not None:
                                        reg2.set_gauge("prompt_studio.jobs.duration_p90_seconds", float(p90), labels)
                                    if p99 is not None:
                                        reg2.set_gauge("prompt_studio.jobs.duration_p99_seconds", float(p99), labels)
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
                    # Reconcile into job_counters (SQLite)
                    try:
                        if str(os.getenv("JOBS_COUNTERS_RECONCILE", "")).lower() in {"1","true","yes","y","on"}:
                            qrc = (
                                "SELECT domain, queue, job_type, "
                                "SUM(CASE WHEN status='queued' AND (available_at IS NULL OR available_at <= DATETIME('now')) THEN 1 ELSE 0 END) AS q_ready, "
                                "SUM(CASE WHEN status='queued' AND (available_at IS NOT NULL AND available_at > DATETIME('now')) THEN 1 ELSE 0 END) AS q_sched, "
                                "SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS p, "
                                "SUM(CASE WHEN status='quarantined' THEN 1 ELSE 0 END) AS qz "
                                "FROM jobs GROUP BY domain, queue, job_type"
                            )
                            for (d, q, jt, rdy, sch, proc, qz) in conn.execute(qrc).fetchall() or []:
                                try:
                                    conn.execute(
                                        (
                                            "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(?,?,?,?,?,?,?) "
                                            "ON CONFLICT(domain,queue,job_type) DO UPDATE SET ready_count = ?, scheduled_count = ?, processing_count = ?, quarantined_count = ?, updated_at = DATETIME('now')"
                                        ),
                                        (str(d), str(q), str(jt), int(rdy or 0), int(sch or 0), int(proc or 0), int(qz or 0), int(rdy or 0), int(sch or 0), int(proc or 0), int(qz or 0)),
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    # Audio jobs by owner/status
                    try:
                        q3 = "SELECT owner_user_id, status, COUNT(*) FROM jobs WHERE domain=? GROUP BY owner_user_id, status"
                        rows = conn.execute(q3, ("audio",)).fetchall() or []
                        try:
                            reg = get_metrics_registry()
                            for (owner_user_id, status, count) in rows:
                                reg.set_gauge("audio.jobs.by_owner_status", int(count or 0), {"owner_user_id": str(owner_user_id or ""), "status": str(status or "")})
                        except Exception:
                            pass
                    except Exception:
                        pass
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
                    # SLO percentiles for SQLite (approximate, windowed, limited groups)
                    if slo_enabled:
                        try:
                            window_clause = f"DATETIME('now','-{int(slo_window_h)} hours')"
                            # Queue latency rows
                            q = (
                                "SELECT domain, queue, job_type, owner_user_id, "
                                "(julianday(acquired_at) - julianday(created_at)) * 86400.0 AS lat "
                                "FROM jobs WHERE acquired_at IS NOT NULL AND created_at >= " + window_clause
                            )
                            rows = conn.execute(q).fetchall() or []
                            groups: dict[tuple[str,str,str,str], list[float]] = {}
                            for (domain, queue, job_type, owner, lat) in rows:
                                key = (str(domain), str(queue), str(job_type), str(owner or ""))
                                groups.setdefault(key, []).append(float(lat or 0.0))
                            # Limit groups
                            keys = list(groups.keys())[:slo_max_groups]
                            from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                            reg = get_metrics_registry()
                            for key in keys:
                                vals = sorted(groups[key])
                                if not vals:
                                    continue
                                def pct(p: float) -> float:
                                    if not vals:
                                        return 0.0
                                    idx = max(0, min(len(vals)-1, int(round(p * (len(vals)-1)))))
                                    return float(vals[idx])
                                labels = {"domain": key[0], "queue": key[1], "job_type": key[2], "owner_user_id": key[3]}
                                reg.set_gauge("prompt_studio.jobs.queue_latency_p50_seconds", pct(0.5), labels)
                                reg.set_gauge("prompt_studio.jobs.queue_latency_p90_seconds", pct(0.9), labels)
                                reg.set_gauge("prompt_studio.jobs.queue_latency_p99_seconds", pct(0.99), labels)
                        except Exception:
                            pass
                        try:
                            # Durations from completed
                            qd = (
                                "SELECT domain, queue, job_type, owner_user_id, "
                                "(julianday(completed_at) - julianday(COALESCE(started_at, acquired_at))) * 86400.0 AS dur "
                                "FROM jobs WHERE completed_at IS NOT NULL AND created_at >= " + window_clause
                            )
                            rowsd = conn.execute(qd).fetchall() or []
                            groupsd: dict[tuple[str,str,str,str], list[float]] = {}
                            for (domain, queue, job_type, owner, dur) in rowsd:
                                key = (str(domain), str(queue), str(job_type), str(owner or ""))
                                groupsd.setdefault(key, []).append(float(dur or 0.0))
                            keysd = list(groupsd.keys())[:slo_max_groups]
                            from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                            regd = get_metrics_registry()
                            for key in keysd:
                                vals = sorted(groupsd[key])
                                if not vals:
                                    continue
                                def pct(p: float) -> float:
                                    if not vals:
                                        return 0.0
                                    idx = max(0, min(len(vals)-1, int(round(p * (len(vals)-1)))))
                                    return float(vals[idx])
                                labels = {"domain": key[0], "queue": key[1], "job_type": key[2], "owner_user_id": key[3]}
                                regd.set_gauge("prompt_studio.jobs.duration_p50_seconds", pct(0.5), labels)
                                regd.set_gauge("prompt_studio.jobs.duration_p90_seconds", pct(0.9), labels)
                                regd.set_gauge("prompt_studio.jobs.duration_p99_seconds", pct(0.99), labels)
                        except Exception:
                            pass
                # Apply TTL policies if enabled (leader-elected per domain/queue on Postgres)
                if ttl_enforce and (ttl_age or ttl_runtime):
                    try:
                        if jm.backend == "postgres":
                            with jm._pg_cursor(conn) as cur:
                                cur.execute("SELECT DISTINCT domain, queue FROM jobs")
                                rows = cur.fetchall() or []
                            for r in rows:
                                d = str(r[0]); q = str(r[1])
                                key = jm._pg_advisory_key("ttl", d, q)
                                if not jm._pg_try_advisory_lock(key):
                                    continue
                                try:
                                    jm.apply_ttl_policies(age_seconds=ttl_age, runtime_seconds=ttl_runtime, action=ttl_action, domain=d, queue=q)
                                finally:
                                    try:
                                        jm._pg_advisory_unlock(key)
                                    except Exception:
                                        pass
                        else:
                            jm.apply_ttl_policies(age_seconds=ttl_age, runtime_seconds=ttl_runtime, action=ttl_action)
                    except Exception as _e:
                        logger.debug(f"TTL sweep error: {_e}")

                # Optional prune by retention tiers (leader-elected per domain/queue on Postgres)
                if prune_enforce and (retention_terminal_days > 0 or retention_nonterminal_days > 0):
                    try:
                        if jm.backend == "postgres":
                            with jm._pg_cursor(conn) as cur:
                                cur.execute("SELECT DISTINCT domain, queue FROM jobs")
                                dq_rows = cur.fetchall() or []
                            for r in dq_rows:
                                d = str(r[0]); q = str(r[1])
                                key = jm._pg_advisory_key("prune", d, q)
                                if not jm._pg_try_advisory_lock(key):
                                    continue
                                try:
                                    if retention_terminal_days > 0:
                                        jm.prune_jobs(statuses=["completed","failed","cancelled","quarantined"], older_than_days=int(retention_terminal_days), domain=d, queue=q)
                                    if retention_nonterminal_days > 0:
                                        # Dangerous; disabled by default. When configured, will prune very old queued/processing (stuck) items.
                                        jm.prune_jobs(statuses=["queued","processing"], older_than_days=int(retention_nonterminal_days), domain=d, queue=q)
                                finally:
                                    try:
                                        jm._pg_advisory_unlock(key)
                                    except Exception:
                                        pass
                        else:
                            if retention_terminal_days > 0:
                                jm.prune_jobs(statuses=["completed","failed","cancelled","quarantined"], older_than_days=int(retention_terminal_days))
                            if retention_nonterminal_days > 0:
                                jm.prune_jobs(statuses=["queued","processing"], older_than_days=int(retention_nonterminal_days))
                    except Exception as _e:
                        logger.debug(f"Prune sweep error: {_e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Jobs metrics gauge loop error: {e}")

        await asyncio.sleep(interval)
