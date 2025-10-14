from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.metrics import ensure_jobs_metrics_registered


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
                else:
                    q = (
                        "SELECT domain, queue, COUNT(*) as c FROM jobs "
                        "WHERE status='processing' AND (leased_until IS NULL OR leased_until <= DATETIME('now')) "
                        "GROUP BY domain, queue"
                    )
                    for (domain, queue, c) in conn.execute(q).fetchall():
                        set_stale_processing(str(domain), str(queue), int(c))
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Jobs metrics gauge loop error: {e}")

        await asyncio.sleep(interval)

