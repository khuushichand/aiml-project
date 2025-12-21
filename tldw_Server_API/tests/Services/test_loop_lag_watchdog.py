import asyncio
import time
from unittest.mock import patch

import pytest

from tldw_Server_API.app.services.loop_lag_watchdog import run_loop_lag_watchdog


@pytest.mark.asyncio
async def test_loop_lag_watchdog_logs_on_block(monkeypatch):
    monkeypatch.setenv("EVENT_LOOP_LAG_WATCHDOG_ENABLED", "true")
    monkeypatch.setenv("EVENT_LOOP_LAG_THRESHOLD_MS", "5")
    monkeypatch.setenv("EVENT_LOOP_LAG_INTERVAL_MS", "10")
    monkeypatch.setenv("EVENT_LOOP_LAG_LOG_THROTTLE_MS", "0")

    stop_event = asyncio.Event()
    with patch("tldw_Server_API.app.services.loop_lag_watchdog.logger") as mock_logger:
        task = asyncio.create_task(run_loop_lag_watchdog(stop_event))
        await asyncio.sleep(0.02)
        # Force a blocking gap on the loop to trigger lag logging.
        time.sleep(0.05)
        await asyncio.sleep(0.05)
        stop_event.set()
        await asyncio.wait_for(task, timeout=1.0)

        assert mock_logger.warning.called
