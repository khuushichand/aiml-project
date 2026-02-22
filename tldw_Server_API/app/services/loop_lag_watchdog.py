from __future__ import annotations

import asyncio
import os

from loguru import logger
from tldw_Server_API.app.core.testing import is_truthy


def _is_truthy(value: str | None) -> bool:
    return is_truthy(str(value or "").strip().lower())


async def run_loop_lag_watchdog(stop_event: asyncio.Event | None = None) -> None:
    """Log event-loop lag when the loop is blocked beyond a threshold.

    Env vars:
      - EVENT_LOOP_LAG_WATCHDOG_ENABLED=true|false
      - EVENT_LOOP_LAG_THRESHOLD_MS=200
      - EVENT_LOOP_LAG_INTERVAL_MS=250
      - EVENT_LOOP_LAG_LOG_THROTTLE_MS=5000
    """
    if not _is_truthy(os.getenv("EVENT_LOOP_LAG_WATCHDOG_ENABLED", "")):
        return

    def _coerce_int(raw: str | None, default: int) -> int:
        try:
            return int(str(raw or "").strip() or default)
        except (TypeError, ValueError):
            return default

    threshold_ms = _coerce_int(os.getenv("EVENT_LOOP_LAG_THRESHOLD_MS"), 200)
    interval_ms = _coerce_int(os.getenv("EVENT_LOOP_LAG_INTERVAL_MS"), 250)
    throttle_ms = _coerce_int(os.getenv("EVENT_LOOP_LAG_LOG_THROTTLE_MS"), 5000)

    interval_s = max(interval_ms / 1000.0, 0.01)
    threshold_s = max(threshold_ms / 1000.0, 0.0)
    throttle_s = max(throttle_ms / 1000.0, 0.0)

    loop = asyncio.get_running_loop()
    last_tick = loop.time()
    last_log = 0.0

    logger.info(
        "Event loop lag watchdog enabled (threshold={}ms interval={}ms throttle={}ms)",
        threshold_ms,
        interval_ms,
        throttle_ms,
    )

    while True:
        if stop_event and stop_event.is_set():
            logger.info("Stopping event loop lag watchdog on shutdown signal")
            return
        await asyncio.sleep(interval_s)
        now = loop.time()
        expected = last_tick + interval_s
        lag = max(0.0, now - expected)
        if lag >= threshold_s and (throttle_s <= 0 or (now - last_log) >= throttle_s):
            logger.warning(
                "Event loop lag detected: {:.1f}ms (threshold {}ms, interval {}ms)",
                lag * 1000.0,
                threshold_ms,
                interval_ms,
            )
            last_log = now
        last_tick = now
