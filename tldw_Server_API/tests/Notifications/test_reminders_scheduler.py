from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.services.reminders_scheduler import (
    REMINDERS_DOMAIN,
    REMINDER_JOB_TYPE,
    _RemindersScheduler,
    _normalize_slot_to_utc_iso,
)


pytestmark = pytest.mark.unit


@pytest.fixture()
def reminders_scheduler_env(monkeypatch, tmp_path):
    base_dir = tmp_path / "test_reminders_scheduler"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("JOBS_DB_PATH", str(base_dir / "jobs.db"))
    try:
        yield
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def _create_recurring_task(user_id: int, *, cron: str = "*/5 * * * *", timezone_name: str = "UTC") -> str:
    cdb = CollectionsDatabase.for_user(user_id=user_id)
    return cdb.create_reminder_task(
        title="Recurring Reminder",
        body="Check this item",
        schedule_kind="recurring",
        run_at=None,
        cron=cron,
        timezone=timezone_name,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_due_slot_enqueues_job_once(reminders_scheduler_env, monkeypatch: pytest.MonkeyPatch):
    user_id = 880
    task_id = _create_recurring_task(user_id)
    cdb = CollectionsDatabase.for_user(user_id=user_id)
    due = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    cdb.update_reminder_task(task_id, {"next_run_at": due.isoformat()})

    scheduler = _RemindersScheduler()
    created: list[dict[str, object]] = []

    def _capture_create_job(**kwargs):
        created.append(kwargs)
        return {"id": 1}

    monkeypatch.setattr(scheduler._jobs, "create_job", _capture_create_job)

    await scheduler._run_task_schedule(task_id, user_id=user_id)

    assert len(created) == 1
    assert created[0]["domain"] == REMINDERS_DOMAIN
    assert created[0]["job_type"] == REMINDER_JOB_TYPE
    assert created[0]["owner_user_id"] == user_id
    assert created[0]["idempotency_key"] == f"task:{task_id}:{_normalize_slot_to_utc_iso(due)}"


@pytest.mark.asyncio
async def test_due_slot_concurrent_scheduler_enqueues_single_job(reminders_scheduler_env):
    user_id = 881
    task_id = _create_recurring_task(user_id)
    cdb = CollectionsDatabase.for_user(user_id=user_id)
    due = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    cdb.update_reminder_task(task_id, {"next_run_at": due.isoformat()})

    sched_a = _RemindersScheduler()
    sched_b = _RemindersScheduler()
    await asyncio.gather(
        sched_a._run_task_schedule(task_id, user_id=user_id),
        sched_b._run_task_schedule(task_id, user_id=user_id),
    )

    jm = JobManager()
    jobs = jm.list_jobs(domain=REMINDERS_DOMAIN, job_type=REMINDER_JOB_TYPE)
    assert len(jobs) == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-11-01T01:30:00-04:00", "2026-11-01T05:30:00+00:00"),
        ("2026-11-01T01:30:00-05:00", "2026-11-01T06:30:00+00:00"),
        ("2026-03-08T02:30:00-05:00", "2026-03-08T07:30:00+00:00"),
    ],
)
def test_normalize_slot_to_utc_iso_handles_dst_offsets(raw: str, expected: str):
    assert _normalize_slot_to_utc_iso(datetime.fromisoformat(raw)) == expected


def test_normalize_slot_to_utc_iso_handles_naive_local_dst_edges():
    ambiguous = _normalize_slot_to_utc_iso(
        datetime(2026, 11, 1, 1, 30, 0),
        timezone_name="America/New_York",
    )
    non_existent = _normalize_slot_to_utc_iso(
        datetime(2026, 3, 8, 2, 30, 0),
        timezone_name="America/New_York",
    )
    assert ambiguous == "2026-11-01T05:30:00+00:00"
    assert non_existent == "2026-03-08T07:30:00+00:00"


@pytest.mark.asyncio
async def test_reconcile_task_adds_enabled_task_when_scheduler_started(reminders_scheduler_env, monkeypatch):
    user_id = 883
    task_id = _create_recurring_task(user_id)
    scheduler = _RemindersScheduler()

    class _FakeAPS:
        def __init__(self) -> None:
            self.removed: list[str] = []

        def remove_job(self, job_id: str) -> None:
            self.removed.append(job_id)

    scheduler._aps = _FakeAPS()
    scheduler._started = True

    adds: list[tuple[str, int]] = []

    def _capture_add(task, user_id: int | None = None):
        adds.append((task.id, int(user_id or 0)))

    monkeypatch.setattr(scheduler, "_add_job", _capture_add)

    await scheduler.reconcile_task(task_id=task_id, user_id=user_id)

    assert adds == [(task_id, user_id)]


@pytest.mark.asyncio
async def test_reconcile_task_removes_disabled_task_when_scheduler_started(reminders_scheduler_env):
    user_id = 884
    task_id = _create_recurring_task(user_id)
    cdb = CollectionsDatabase.for_user(user_id=user_id)
    cdb.update_reminder_task(task_id, {"enabled": False})
    scheduler = _RemindersScheduler()

    class _FakeAPS:
        def __init__(self) -> None:
            self.removed: list[str] = []

        def remove_job(self, job_id: str) -> None:
            self.removed.append(job_id)

    fake_aps = _FakeAPS()
    scheduler._aps = fake_aps
    scheduler._started = True

    await scheduler.reconcile_task(task_id=task_id, user_id=user_id)

    assert fake_aps.removed == [task_id]
