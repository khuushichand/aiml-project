"""
Idempotency behavior tests for Memory backend to ensure scheduler returns
the canonical task ID for duplicate submissions.
"""

import pytest
from pathlib import Path

from ..scheduler import Scheduler
from ..base.registry import get_registry
from ..config import SchedulerConfig


@pytest.mark.asyncio
async def test_memory_backend_idempotency_returns_same_id(tmp_path: Path):
    cfg = SchedulerConfig(
        database_url="memory://",
        base_path=tmp_path,
        min_workers=0,
        max_workers=0,
    )

    scheduler = Scheduler(cfg)
    await scheduler.start(start_workers=False)
    try:
        registry = get_registry()

        @registry.task(name="mem_idem_handler")
        async def handler(payload):
            return payload

        first = await scheduler.submit(
            handler="mem_idem_handler",
            payload={"x": 1},
            idempotency_key="mem-idem-key",
        )
        second = await scheduler.submit(
            handler="mem_idem_handler",
            payload={"x": 2},
            idempotency_key="mem-idem-key",
        )

        assert first == second

        task = await scheduler.get_task(first)
        assert task is not None
        assert task.handler == "mem_idem_handler"

    finally:
        await scheduler.stop()

