import asyncio
import contextlib
from types import SimpleNamespace

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


@pytest.mark.asyncio
async def test_purge_for_user_uses_managed_media_database(monkeypatch):
    events = []

    class _FakeBackend:
        def __init__(self):
            self.delete_calls = []

        def execute(self, query, params):
            if "retention_until" in query:
                return SimpleNamespace(rows=[{"id": 12, "storage_path": "reports/file.txt"}])
            if "deleted = 1" in query:
                return SimpleNamespace(rows=[])
            if query.startswith("DELETE FROM outputs"):
                self.delete_calls.append((query, params))
                return SimpleNamespace(rows=[])
            raise AssertionError(f"Unexpected query: {query}")

    class _FakeMediaDb:
        def mark_tts_history_artifacts_deleted_for_output(self, **kwargs):
            events.append(("mark", kwargs))

    @contextlib.contextmanager
    def _fake_managed_media_database(client_id, **kwargs):
        events.append(("open", client_id, kwargs))
        yield _FakeMediaDb()

    fake_backend = _FakeBackend()
    fake_cdb = SimpleNamespace(backend=fake_backend)

    monkeypatch.setattr(
        scheduler.CollectionsDatabase,
        "for_user",
        lambda user_id: fake_cdb,
    )
    monkeypatch.setattr(
        scheduler.DatabasePaths,
        "get_media_db_path",
        lambda user_id: f"/tmp/media-{user_id}.db",
    )
    monkeypatch.setattr(
        scheduler,
        "MediaDatabase",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("outputs_purge should not construct MediaDatabase directly")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        scheduler,
        "managed_media_database",
        _fake_managed_media_database,
        raising=False,
    )
    monkeypatch.setattr(
        scheduler,
        "get_metrics_registry",
        lambda: SimpleNamespace(increment=lambda *args, **kwargs: None),
    )

    removed, files_deleted = await scheduler._purge_for_user(
        user_id=42,
        delete_files=False,
        grace_days=30,
    )

    assert (removed, files_deleted) == (1, 0)
    assert events == [
        ("open", "outputs_purge", {"db_path": "/tmp/media-42.db", "initialize": False}),
        (
            "mark",
            {
                "user_id": "42",
                "output_id": 12,
            },
        ),
    ]
    assert len(fake_backend.delete_calls) == 1
