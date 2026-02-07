import asyncio

import pytest

from tldw_Server_API.app.core.Chat import chat_service


@pytest.mark.asyncio
async def test_schedule_background_task_tracks_and_cleans_pending():
    pending: list[asyncio.Task] = []
    done = asyncio.Event()

    async def _work():
        await asyncio.sleep(0)
        done.set()
        return 1

    task = chat_service._schedule_background_task(
        _work(),
        task_name="test.pending",
        pending_tasks=pending,
    )

    assert task is not None
    assert task in pending
    await done.wait()
    await asyncio.sleep(0)
    assert task not in pending


@pytest.mark.asyncio
async def test_schedule_background_task_observes_exceptions(monkeypatch):
    captured: list[tuple[str, tuple]] = []

    class _DummyLogger:
        def debug(self, message, *args):
            captured.append((message, args))

    monkeypatch.setattr(chat_service, "logger", _DummyLogger())

    async def _boom():
        raise RuntimeError("boom")

    task = chat_service._schedule_background_task(
        _boom(),
        task_name="test.exception",
    )

    assert task is not None
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0)
    assert any("test.exception" in str(args) for _, args in captured)


@pytest.mark.asyncio
async def test_schedule_background_task_cancelled_is_silent(monkeypatch):
    captured: list[tuple[str, tuple]] = []

    class _DummyLogger:
        def debug(self, message, *args):
            captured.append((message, args))

    monkeypatch.setattr(chat_service, "logger", _DummyLogger())

    async def _slow():
        await asyncio.sleep(5)

    task = chat_service._schedule_background_task(
        _slow(),
        task_name="test.cancel",
    )

    assert task is not None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    assert not any("test.cancel" in str(args) and "failed" in msg for msg, args in captured)
