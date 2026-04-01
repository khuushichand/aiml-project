from __future__ import annotations

import asyncio
from collections.abc import Iterable
from concurrent.futures import Executor
from threading import RLock

from loguru import logger

_registry_lock = RLock()
_executors: dict[str, Executor] = {}
_EXECUTOR_SHUTDOWN_PRIORITIES: dict[str, int] = {
    "db_thread_pool": 100,
}


def register_executor(name: str, executor: Executor) -> None:
    """Register an executor for coordinated shutdown."""
    with _registry_lock:
        existing = _executors.get(name)
        if existing is executor:
            return
        if existing and existing is not executor:
            logger.warning(
                f"Executor registry replacing existing executor for name='{name}'",
                name=name,
            )
        _executors[name] = executor


def unregister_executor(name: str) -> None:
    """Remove an executor from the registry without shutting it down."""
    with _registry_lock:
        _executors.pop(name, None)


def _snapshot() -> Iterable[tuple[str, Executor]]:
    with _registry_lock:
        return list(_executors.items())


def _ordered_shutdown_snapshot() -> list[tuple[str, Executor]]:
    snapshot = list(_snapshot())
    snapshot.sort(key=lambda item: _EXECUTOR_SHUTDOWN_PRIORITIES.get(item[0], 0))
    return snapshot


def snapshot_registered_executors() -> tuple[tuple[str, Executor], ...]:
    """Expose a stable snapshot of registered executors for shutdown coordination."""
    return tuple(_snapshot())


def _shutdown_executor_blocking(name: str, executor: Executor, wait: bool, cancel_futures: bool) -> None:
    """Shutdown helper that runs in a worker thread when awaited."""
    try:
        try:
            executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        except TypeError:
            # Python <3.9 compatibility
            executor.shutdown(wait=wait)
        # Logging during interpreter shutdown frequently hits pytest's closed
        # capture streams, so skip the informational log to avoid noisy errors.
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(f"Executor '{name}' shutdown raised: {exc}", name=name, exc=exc)
    finally:
        unregister_executor(name)


async def shutdown_executor(name: str, wait: bool = True, cancel_futures: bool = True) -> None:
    """Shutdown a specific registered executor."""
    with _registry_lock:
        executor = _executors.get(name)
    if executor is None:
        return
    await asyncio.to_thread(_shutdown_executor_blocking, name, executor, wait, cancel_futures)


async def shutdown_all_registered_executors(wait: bool = True, cancel_futures: bool = True) -> None:
    """Shutdown all registered executors in dependency-aware order."""
    snapshot = _ordered_shutdown_snapshot()
    if not snapshot:
        return
    for name, executor in snapshot:
        await asyncio.to_thread(_shutdown_executor_blocking, name, executor, wait, cancel_futures)


def shutdown_executor_sync(name: str, wait: bool = True, cancel_futures: bool = True) -> None:
    """Synchronous counterpart for atexit handlers."""
    with _registry_lock:
        executor = _executors.get(name)
    if executor is None:
        return
    _shutdown_executor_blocking(name, executor, wait, cancel_futures)


def shutdown_all_registered_executors_sync(wait: bool = True, cancel_futures: bool = True) -> None:
    """Synchronous shutdown for environments without an event loop."""
    for name, executor in _ordered_shutdown_snapshot():
        _shutdown_executor_blocking(name, executor, wait, cancel_futures)
