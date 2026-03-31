from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Executor

import pytest


pytestmark = pytest.mark.unit


class _BlockingExecutor(Executor):
    def __init__(self, started: threading.Event, release: threading.Event, started_count: list[int]) -> None:
        self._started = started
        self._release = release
        self._started_count = started_count

    def shutdown(self, wait: bool = True, cancel_futures: bool = True) -> None:
        self._started_count[0] += 1
        if self._started_count[0] >= 2:
            self._started.set()
        self._release.wait(timeout=1.0)


def test_snapshot_registered_executors_exposes_registered_names() -> None:
    from tldw_Server_API.app.core.Utils.executor_registry import (
        register_executor,
        snapshot_registered_executors,
        unregister_executor,
    )

    first = _BlockingExecutor(threading.Event(), threading.Event(), [0])
    second = _BlockingExecutor(threading.Event(), threading.Event(), [0])
    register_executor("alpha", first)
    register_executor("beta", second)

    try:
        snapshot = dict(snapshot_registered_executors())

        assert snapshot["alpha"] is first
        assert snapshot["beta"] is second
    finally:
        unregister_executor("alpha")
        unregister_executor("beta")


@pytest.mark.asyncio
async def test_shutdown_all_registered_executors_runs_shutdowns_concurrently() -> None:
    from tldw_Server_API.app.core.Utils.executor_registry import (
        register_executor,
        shutdown_all_registered_executors,
        unregister_executor,
    )

    started = threading.Event()
    release = threading.Event()
    started_count = [0]
    first = _BlockingExecutor(started, release, started_count)
    second = _BlockingExecutor(started, release, started_count)
    register_executor("alpha", first)
    register_executor("beta", second)

    try:
        shutdown_task = asyncio.create_task(shutdown_all_registered_executors())
        await asyncio.wait_for(asyncio.to_thread(started.wait, 1.0), timeout=1.5)

        assert started_count[0] == 2

        release.set()
        await shutdown_task
    finally:
        unregister_executor("alpha")
        unregister_executor("beta")
