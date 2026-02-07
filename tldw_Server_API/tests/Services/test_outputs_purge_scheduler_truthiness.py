import asyncio
import contextlib

import pytest

import tldw_Server_API.app.services.outputs_purge_scheduler as scheduler


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_outputs_purge_scheduler_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OUTPUTS_PURGE_ENABLED", raising=False)
    task = await scheduler.start_outputs_purge_scheduler()
    assert task is None


@pytest.mark.asyncio
async def test_outputs_purge_scheduler_accepts_y_flags(monkeypatch):
    monkeypatch.setenv("OUTPUTS_PURGE_ENABLED", "y")
    monkeypatch.setenv("OUTPUTS_PURGE_DELETE_FILES", "y")
    monkeypatch.setenv("OUTPUTS_PURGE_INTERVAL_SEC", "1")

    calls: list[tuple[int, bool, int]] = []

    monkeypatch.setattr(scheduler, "_enumerate_user_ids", lambda: [42])

    async def _fake_purge_for_user(user_id: int, delete_files: bool, grace_days: int):
        calls.append((user_id, delete_files, grace_days))
        return (0, 0)

    monkeypatch.setattr(scheduler, "_purge_for_user", _fake_purge_for_user)

    sleep_calls = {"count": 0}

    async def _fake_sleep(_seconds: float):
        sleep_calls["count"] += 1
        # First call is startup delay, second call is loop interval.
        # Cancel the task after one run.
        if sleep_calls["count"] >= 2:
            raise asyncio.CancelledError
        return None

    monkeypatch.setattr(scheduler.asyncio, "sleep", _fake_sleep)

    task = await scheduler.start_outputs_purge_scheduler()
    assert task is not None
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert calls
    assert calls[0] == (42, True, 30)
