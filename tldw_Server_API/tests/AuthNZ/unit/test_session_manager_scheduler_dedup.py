from __future__ import annotations

from types import SimpleNamespace

import pytest


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs: list[dict] = []
        self.started = False

    def add_job(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.jobs.append({"args": args, "kwargs": kwargs})

    def start(self) -> None:
        self.started = True


@pytest.mark.asyncio
async def test_session_manager_does_not_schedule_inline_cleanup_by_default(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import session_manager as sm

    monkeypatch.setattr(sm, "is_test_mode", lambda: False)
    monkeypatch.delenv("AUTHNZ_SCHEDULER_DISABLED", raising=False)
    monkeypatch.delenv("AUTHNZ_SESSION_MANAGER_INLINE_SCHEDULER", raising=False)
    monkeypatch.delenv("AUTHNZ_SCHEDULER_ENABLED", raising=False)
    monkeypatch.setattr(sm.SessionManager, "_init_encryption", lambda self: None, raising=True)

    manager = sm.SessionManager(
        settings=SimpleNamespace(
            REDIS_URL=None,
            REDIS_MAX_CONNECTIONS=10,
            SESSION_CLEANUP_INTERVAL_HOURS=1,
        )
    )
    fake_scheduler = _FakeScheduler()
    manager.scheduler = fake_scheduler

    async def _fake_ensure_db_pool(self):  # noqa: ANN001
        return object()

    monkeypatch.setattr(sm.SessionManager, "_ensure_db_pool", _fake_ensure_db_pool, raising=True)

    await manager.initialize()

    assert fake_scheduler.jobs == []
    assert fake_scheduler.started is False


@pytest.mark.asyncio
async def test_session_manager_schedules_inline_cleanup_when_authnz_scheduler_disabled(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import session_manager as sm

    monkeypatch.setattr(sm, "is_test_mode", lambda: False)
    monkeypatch.setenv("AUTHNZ_SCHEDULER_DISABLED", "true")
    monkeypatch.delenv("AUTHNZ_SESSION_MANAGER_INLINE_SCHEDULER", raising=False)
    monkeypatch.delenv("AUTHNZ_SCHEDULER_ENABLED", raising=False)
    monkeypatch.setattr(sm.SessionManager, "_init_encryption", lambda self: None, raising=True)

    manager = sm.SessionManager(
        settings=SimpleNamespace(
            REDIS_URL=None,
            REDIS_MAX_CONNECTIONS=10,
            SESSION_CLEANUP_INTERVAL_HOURS=1,
        )
    )
    fake_scheduler = _FakeScheduler()
    manager.scheduler = fake_scheduler

    async def _fake_ensure_db_pool(self):  # noqa: ANN001
        return object()

    monkeypatch.setattr(sm.SessionManager, "_ensure_db_pool", _fake_ensure_db_pool, raising=True)

    await manager.initialize()

    assert len(fake_scheduler.jobs) == 1
    assert fake_scheduler.jobs[0]["kwargs"].get("id") == "session_cleanup"
    assert fake_scheduler.started is True
