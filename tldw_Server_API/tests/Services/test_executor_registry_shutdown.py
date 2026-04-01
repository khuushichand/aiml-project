from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Executor

import pytest


pytestmark = pytest.mark.unit


class _BlockingExecutor(Executor):
    def __init__(
        self,
        expected_starts: int,
        started_all: threading.Event,
        release: threading.Event,
        started_count: list[int],
        started_lock: threading.Lock,
    ) -> None:
        self._expected_starts = expected_starts
        self._started_all = started_all
        self._release = release
        self._started_count = started_count
        self._started_lock = started_lock

    def shutdown(self, wait: bool = True, cancel_futures: bool = True) -> None:
        del wait, cancel_futures
        with self._started_lock:
            self._started_count[0] += 1
            if self._started_count[0] >= self._expected_starts:
                self._started_all.set()
        self._release.wait()


def test_snapshot_registered_executors_exposes_registered_names() -> None:
    from tldw_Server_API.app.core.Utils.executor_registry import (
        register_executor,
        snapshot_registered_executors,
        unregister_executor,
    )

    started_lock = threading.Lock()
    started_all = threading.Event()
    first = _BlockingExecutor(1, started_all, threading.Event(), [0], started_lock)
    second = _BlockingExecutor(1, started_all, threading.Event(), [0], started_lock)
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

    started_all = threading.Event()
    release = threading.Event()
    started_count = [0]
    started_lock = threading.Lock()
    first = _BlockingExecutor(2, started_all, release, started_count, started_lock)
    second = _BlockingExecutor(2, started_all, release, started_count, started_lock)
    register_executor("alpha", first)
    register_executor("beta", second)

    try:
        shutdown_task = asyncio.create_task(shutdown_all_registered_executors())
        await asyncio.wait_for(asyncio.to_thread(started_all.wait), timeout=1.5)
        assert started_count[0] == 2

        release.set()
        await shutdown_task
    finally:
        unregister_executor("alpha")
        unregister_executor("beta")
