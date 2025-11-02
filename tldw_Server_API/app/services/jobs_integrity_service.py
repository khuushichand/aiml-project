from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager


async def run_jobs_integrity_sweeper(stop_event: Optional[asyncio.Event] = None) -> None:
    """Periodically validate and optionally repair Jobs invariants.

    Controlled by env flags:
      - JOBS_INTEGRITY_SWEEP_ENABLED=true|false
      - JOBS_INTEGRITY_SWEEP_INTERVAL_SEC=60
      - JOBS_INTEGRITY_SWEEP_FIX=true|false (when true, attempts self-heal)
    """
    if str(os.getenv("JOBS_INTEGRITY_SWEEP_ENABLED", "")).lower() not in {"1","true","yes","y","on"}:
        return

    interval = float(os.getenv("JOBS_INTEGRITY_SWEEP_INTERVAL_SEC", "60") or "60")
    do_fix = str(os.getenv("JOBS_INTEGRITY_SWEEP_FIX", "")).lower() in {"1","true","yes","y","on"}
    jm = JobManager()
    logger.info(f"Starting Jobs integrity sweeper (every {interval}s, fix={do_fix})")
    while True:
        try:
            if stop_event and stop_event.is_set():
                logger.info("Stopping Jobs integrity sweeper on shutdown signal")
                return
            stats = jm.integrity_sweep(fix=do_fix)
            try:
                logger.debug(f"Jobs integrity sweep: {stats}")
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Jobs integrity sweep error: {e}")
        await asyncio.sleep(interval)
