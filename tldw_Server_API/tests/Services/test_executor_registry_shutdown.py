from __future__ import annotations

import asyncio
from concurrent.futures import Executor

import pytest


pytestmark = pytest.mark.unit


class _RecordingExecutor(Executor):
    def __init__(self, name: str, shutdown_order: list[str]) -> None:
        self._name = name
        self._shutdown_order = shutdown_order

    def shutdown(self, wait: bool = True, cancel_futures: bool = True) -> None:
        del wait, cancel_futures
        self._shutdown_order.append(self._name)


def test_snapshot_registered_executors_exposes_registered_names() -> None:
    from tldw_Server_API.app.core.Utils.executor_registry import (
        register_executor,
        snapshot_registered_executors,
        unregister_executor,
    )

    shutdown_order: list[str] = []
    first = _RecordingExecutor("alpha", shutdown_order)
    second = _RecordingExecutor("beta", shutdown_order)
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
async def test_shutdown_all_registered_executors_shuts_db_pool_down_last() -> None:
    from tldw_Server_API.app.core.Utils.executor_registry import (
        register_executor,
        shutdown_all_registered_executors,
        unregister_executor,
    )

    shutdown_order: list[str] = []
    db_executor = _RecordingExecutor("db_thread_pool", shutdown_order)
    cpu_thread_executor = _RecordingExecutor("cpu_thread_pool", shutdown_order)
    cpu_process_executor = _RecordingExecutor("cpu_process_pool", shutdown_order)
    register_executor("db_thread_pool", db_executor)
    register_executor("cpu_thread_pool", cpu_thread_executor)
    register_executor("cpu_process_pool", cpu_process_executor)

    try:
        await shutdown_all_registered_executors()
        assert shutdown_order == ["cpu_thread_pool", "cpu_process_pool", "db_thread_pool"]
    finally:
        unregister_executor("db_thread_pool")
        unregister_executor("cpu_thread_pool")
        unregister_executor("cpu_process_pool")
