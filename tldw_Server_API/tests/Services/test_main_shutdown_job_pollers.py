import asyncio

import pytest

from tldw_Server_API.app.services import admin_backup_jobs_worker
from tldw_Server_API.app.services import admin_byok_validation_jobs_worker
from tldw_Server_API.app.services import connectors_worker
from tldw_Server_API.app.services import reminder_jobs_worker


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_start_connectors_worker_uses_caller_owned_stop_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    stop_event = asyncio.Event()

    async def _fake_run(stop_event_arg: asyncio.Event | None = None) -> None:
        observed["stop_event"] = stop_event_arg
        await stop_event_arg.wait()

    monkeypatch.setenv("CONNECTORS_WORKER_ENABLED", "1")
    monkeypatch.setattr(connectors_worker, "run_connectors_worker", _fake_run)

    task = await connectors_worker.start_connectors_worker(stop_event=stop_event)
    assert task is not None
    await asyncio.sleep(0)

    assert observed["stop_event"] is stop_event

    stop_event.set()
    await asyncio.wait_for(task, timeout=1)


@pytest.mark.asyncio
async def test_start_reminder_jobs_worker_uses_caller_owned_stop_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    stop_event = asyncio.Event()

    async def _fake_run(stop_event_arg: asyncio.Event | None = None) -> None:
        observed["stop_event"] = stop_event_arg
        await stop_event_arg.wait()

    monkeypatch.setenv("REMINDER_JOBS_WORKER_ENABLED", "1")
    monkeypatch.setattr(reminder_jobs_worker, "run_reminder_jobs_worker", _fake_run)

    task = await reminder_jobs_worker.start_reminder_jobs_worker(stop_event=stop_event)
    assert task is not None
    await asyncio.sleep(0)

    assert observed["stop_event"] is stop_event

    stop_event.set()
    await asyncio.wait_for(task, timeout=1)


@pytest.mark.asyncio
async def test_run_admin_backup_jobs_worker_stops_sdk_when_stop_event_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop_event = asyncio.Event()
    observed = {"stopped": False}

    class _FakeWorkerSDK:
        def __init__(self, _jm, _cfg) -> None:
            pass

        def stop(self) -> None:
            observed["stopped"] = True

        async def run(self, *, handler) -> None:
            while not observed["stopped"]:
                await asyncio.sleep(0)

    monkeypatch.setattr(admin_backup_jobs_worker, "WorkerSDK", _FakeWorkerSDK)

    task = asyncio.create_task(admin_backup_jobs_worker.run_admin_backup_jobs_worker(stop_event))
    await asyncio.sleep(0)
    stop_event.set()
    await asyncio.wait_for(task, timeout=1)

    assert observed["stopped"] is True


@pytest.mark.asyncio
async def test_start_admin_backup_jobs_worker_forwards_caller_owned_stop_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    stop_event = asyncio.Event()

    async def _fake_run(stop_event_arg: asyncio.Event | None = None) -> None:
        observed["stop_event"] = stop_event_arg
        await stop_event_arg.wait()

    monkeypatch.setenv("ADMIN_BACKUP_JOBS_WORKER_ENABLED", "1")
    monkeypatch.setattr(admin_backup_jobs_worker, "run_admin_backup_jobs_worker", _fake_run)

    task = await admin_backup_jobs_worker.start_admin_backup_jobs_worker(stop_event=stop_event)
    assert task is not None
    await asyncio.sleep(0)

    assert observed["stop_event"] is stop_event

    stop_event.set()
    await asyncio.wait_for(task, timeout=1)


@pytest.mark.asyncio
async def test_run_admin_byok_validation_jobs_worker_stops_sdk_when_stop_event_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop_event = asyncio.Event()
    observed = {"stopped": False}

    class _FakeWorkerSDK:
        def __init__(self, _jm, _cfg) -> None:
            pass

        def stop(self) -> None:
            observed["stopped"] = True

        async def run(self, *, handler) -> None:
            while not observed["stopped"]:
                await asyncio.sleep(0)

    monkeypatch.setattr(admin_byok_validation_jobs_worker, "WorkerSDK", _FakeWorkerSDK)

    task = asyncio.create_task(
        admin_byok_validation_jobs_worker.run_admin_byok_validation_jobs_worker(stop_event)
    )
    await asyncio.sleep(0)
    stop_event.set()
    await asyncio.wait_for(task, timeout=1)

    assert observed["stopped"] is True


@pytest.mark.asyncio
async def test_start_admin_byok_validation_jobs_worker_forwards_caller_owned_stop_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    stop_event = asyncio.Event()

    async def _fake_run(stop_event_arg: asyncio.Event | None = None) -> None:
        observed["stop_event"] = stop_event_arg
        await stop_event_arg.wait()

    monkeypatch.setenv("ADMIN_BYOK_VALIDATION_JOBS_WORKER_ENABLED", "1")
    monkeypatch.setattr(
        admin_byok_validation_jobs_worker,
        "run_admin_byok_validation_jobs_worker",
        _fake_run,
    )

    task = await admin_byok_validation_jobs_worker.start_admin_byok_validation_jobs_worker(
        stop_event=stop_event
    )
    assert task is not None
    await asyncio.sleep(0)

    assert observed["stop_event"] is stop_event

    stop_event.set()
    await asyncio.wait_for(task, timeout=1)
