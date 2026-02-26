from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.Jobs.event_stream import emit_job_event
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.services.jobs_notifications_service import JobsNotificationsService


pytestmark = pytest.mark.unit


@pytest.fixture()
def jobs_notifications_env(monkeypatch, tmp_path):
    base_dir = tmp_path / "test_jobs_notifications_service"
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("JOBS_DB_PATH", str(base_dir / "jobs.db"))
    monkeypatch.setenv("JOBS_EVENTS_OUTBOX", "true")
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


@pytest.mark.asyncio
async def test_job_completed_event_creates_notification(jobs_notifications_env):
    user_id = 991
    service = JobsNotificationsService(bridge_state_user_id=user_id, lease_owner_id="bridge-test")
    event = {
        "id": 10,
        "event_type": "job.completed",
        "job_id": 55,
        "domain": "chatbooks",
        "queue": "default",
        "job_type": "export",
        "owner_user_id": str(user_id),
        "attrs_json": "{}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    row = await service.process_event(event)

    assert row is not None
    assert row.kind == "job_completed"
    assert row.source_job_id == "55"


@pytest.mark.asyncio
async def test_run_once_advances_cursor_and_creates_failed_notification(jobs_notifications_env):
    user_id = 992
    cdb = CollectionsDatabase.for_user(user_id=user_id)
    cdb.update_notification_preferences(job_failed_enabled=True)
    service = JobsNotificationsService(
        bridge_state_user_id=user_id,
        lease_owner_id="bridge-run-once",
        consumer_name="jobs_notifications_test",
        poll_batch_size=50,
    )

    jm = JobManager()
    job = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id=str(user_id),
    )
    emit_job_event(
        "job.failed",
        job={
            "id": int(job["id"]),
            "domain": "chatbooks",
            "queue": "default",
            "job_type": "export",
            "owner_user_id": str(user_id),
        },
        attrs={"error_code": "boom"},
    )

    summary = await service.run_once()

    assert summary["processed"] >= 1
    assert summary["notifications_created"] >= 1
    rows = cdb.list_user_notifications(limit=20, offset=0)
    assert any(r.kind == "job_failed" and r.source_job_id == str(job["id"]) for r in rows)

    state = cdb.get_notification_bridge_state(consumer_name="jobs_notifications_test")
    assert state.last_event_id > 0

