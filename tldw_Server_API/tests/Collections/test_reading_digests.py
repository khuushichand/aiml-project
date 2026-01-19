import asyncio
import importlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Collections.reading_digest_jobs import (
    READING_DIGEST_DOMAIN,
    READING_DIGEST_JOB_TYPE,
    handle_reading_digest_job,
    reading_digest_queue,
)
from tldw_Server_API.app.services.reading_digest_scheduler import _ReadingDigestScheduler
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch):
    async def override_user():
        return User(id=222, username="reader", email=None, is_active=True)

    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_ENABLE", "reading")

    base_dir = Path.cwd() / "Databases" / "test_reading_digest"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    jobs_db_path = base_dir / "jobs.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(jobs_db_path))
    os.environ["JOBS_DB_PATH"] = str(jobs_db_path)

    from tldw_Server_API.app import main as app_main

    importlib.reload(app_main)
    fastapi_app = app_main.app

    fastapi_app.dependency_overrides[get_request_user] = override_user
    try:
        with TestClient(fastapi_app) as client:
            yield client
    finally:
        fastapi_app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass
        os.environ.pop("JOBS_DB_PATH", None)


def _run_digest_job(job_id: int) -> None:
    async def _runner() -> None:
        jm = JobManager()
        job = jm.get_job(job_id)
        assert job is not None
        result = await handle_reading_digest_job(job)
        jm.complete_job(job_id, result=result, enforce=False)

    asyncio.run(_runner())


def test_reading_digest_schedule_crud(client_with_user):
    client = client_with_user
    payload = {
        "name": "Morning Digest",
        "cron": "0 8 * * *",
        "timezone": "UTC",
        "format": "md",
        "filters": {"status": ["saved"], "tags": ["ai"], "limit": 5},
    }
    create_resp = client.post("/api/v1/reading/digests/schedules", json=payload)
    assert create_resp.status_code == 201, create_resp.text
    schedule_id = create_resp.json()["id"]

    list_resp = client.get("/api/v1/reading/digests/schedules")
    assert list_resp.status_code == 200
    schedules = list_resp.json()
    assert any(row["id"] == schedule_id for row in schedules)

    get_resp = client.get(f"/api/v1/reading/digests/schedules/{schedule_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Morning Digest"

    patch_resp = client.patch(
        f"/api/v1/reading/digests/schedules/{schedule_id}",
        json={"name": "Updated Digest", "enabled": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Digest"
    assert patch_resp.json()["enabled"] is False

    delete_resp = client.delete(f"/api/v1/reading/digests/schedules/{schedule_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["ok"] is True


def test_reading_digest_job_creates_output(client_with_user):
    client = client_with_user
    save_resp = client.post(
        "/api/v1/reading/save",
        json={"url": "https://example.com/article", "title": "Example", "content": "Body"},
    )
    assert save_resp.status_code == 200, save_resp.text

    db = CollectionsDatabase.for_user(user_id=222)
    schedule_id = "digest_test"
    db.create_reading_digest_schedule(
        id=schedule_id,
        tenant_id="default",
        name="Test Digest",
        cron="0 8 * * *",
        timezone="UTC",
        enabled=True,
        require_online=False,
        filters={"status": ["saved"], "limit": 10},
        template_id=None,
        template_name=None,
        format="md",
        retention_days=7,
    )

    jm = JobManager()
    job = jm.create_job(
        domain=READING_DIGEST_DOMAIN,
        queue=reading_digest_queue(),
        job_type=READING_DIGEST_JOB_TYPE,
        payload={"schedule_id": schedule_id, "user_id": 222},
        owner_user_id=222,
    )
    _run_digest_job(job["id"])

    outputs, total = db.list_output_artifacts(type_="reading_digest", limit=10, offset=0)
    assert total == 1
    row = outputs[0]
    meta = json.loads(row.metadata_json or "{}")
    assert meta.get("schedule_id") == schedule_id
    output_path = DatabasePaths.get_user_outputs_dir(222) / row.storage_path
    assert output_path.exists()


def test_reading_digest_scheduler_claims_single_enqueue(client_with_user):
    db = CollectionsDatabase.for_user(user_id=222)
    schedule_id = "digest_claim"
    db.create_reading_digest_schedule(
        id=schedule_id,
        tenant_id="default",
        name="Claim Digest",
        cron="*/5 * * * *",
        timezone="UTC",
        enabled=True,
        require_online=False,
        filters={"status": ["saved"], "limit": 10},
        template_id=None,
        template_name=None,
        format="md",
        retention_days=7,
    )
    tz = ZoneInfo("UTC")
    trigger = CronTrigger.from_crontab("*/5 * * * *", timezone=tz)
    scheduled_dt = trigger.get_next_fire_time(None, datetime.now(tz))
    assert scheduled_dt is not None
    db.set_reading_digest_history(schedule_id, next_run_at=scheduled_dt.isoformat())

    async def _runner() -> None:
        sched_a = _ReadingDigestScheduler()
        sched_b = _ReadingDigestScheduler()
        await asyncio.gather(
            sched_a._run_schedule(schedule_id, user_id=222),
            sched_b._run_schedule(schedule_id, user_id=222),
        )

    asyncio.run(_runner())

    jm = JobManager()
    jobs = jm.list_jobs(domain=READING_DIGEST_DOMAIN, job_type=READING_DIGEST_JOB_TYPE)
    assert len(jobs) == 1
    updated = db.get_reading_digest_schedule(schedule_id)
    assert updated.next_run_at is not None
    updated_dt = datetime.fromisoformat(updated.next_run_at)
    if updated_dt.tzinfo is None:
        updated_dt = updated_dt.replace(tzinfo=timezone.utc)
    if scheduled_dt.tzinfo is None:
        scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
    assert updated_dt > scheduled_dt


@pytest.mark.parametrize(
    ("tz_name", "cron"),
    [
        ("UTC", "0 8 * * *"),
        ("America/New_York", "0 8 * * *"),
    ],
)
def test_reading_digest_next_run_at_timezone(client_with_user, tz_name, cron):
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        pytest.skip(f"Timezone {tz_name} not available in test environment")
    db = CollectionsDatabase.for_user(user_id=222)
    schedule_id = f"digest_tz_{tz_name.replace('/', '_')}"
    db.create_reading_digest_schedule(
        id=schedule_id,
        tenant_id="default",
        name="TZ Digest",
        cron=cron,
        timezone=tz_name,
        enabled=True,
        require_online=False,
        filters={"status": ["saved"], "limit": 5},
        template_id=None,
        template_name=None,
        format="md",
        retention_days=7,
    )
    trigger = CronTrigger.from_crontab(cron, timezone=tz)
    scheduled_dt = trigger.get_next_fire_time(None, datetime.now(tz))
    assert scheduled_dt is not None
    db.set_reading_digest_history(schedule_id, next_run_at=scheduled_dt.isoformat())

    async def _runner() -> None:
        sched = _ReadingDigestScheduler()
        await sched._run_schedule(schedule_id, user_id=222)

    asyncio.run(_runner())

    updated = db.get_reading_digest_schedule(schedule_id)
    assert updated.next_run_at is not None
    updated_dt = datetime.fromisoformat(updated.next_run_at)
    if updated_dt.tzinfo is None:
        pytest.fail("next_run_at missing timezone info")
    if tz_name != "UTC":
        assert updated_dt.utcoffset() is not None
        assert updated_dt.utcoffset().total_seconds() != 0
    assert updated_dt > scheduled_dt


def test_reading_digest_scheduler_skips_disabled_after_claim(client_with_user, monkeypatch):
    db = CollectionsDatabase.for_user(user_id=222)
    schedule_id = "digest_disable_after_claim"
    db.create_reading_digest_schedule(
        id=schedule_id,
        tenant_id="default",
        name="Disable Digest",
        cron="*/15 * * * *",
        timezone="UTC",
        enabled=True,
        require_online=False,
        filters={"status": ["saved"], "limit": 5},
        template_id=None,
        template_name=None,
        format="md",
        retention_days=7,
    )
    tz = ZoneInfo("UTC")
    trigger = CronTrigger.from_crontab("*/15 * * * *", timezone=tz)
    scheduled_dt = trigger.get_next_fire_time(None, datetime.now(tz))
    assert scheduled_dt is not None
    db.set_reading_digest_history(schedule_id, next_run_at=scheduled_dt.isoformat())

    original_claim = CollectionsDatabase.try_claim_reading_digest_run

    def _patched_claim(self, schedule_id: str, **kwargs):
        ok = original_claim(self, schedule_id, **kwargs)
        if ok:
            self.update_reading_digest_schedule(schedule_id, {"enabled": False})
        return ok

    monkeypatch.setattr(CollectionsDatabase, "try_claim_reading_digest_run", _patched_claim)

    async def _runner() -> None:
        sched = _ReadingDigestScheduler()
        await sched._run_schedule(schedule_id, user_id=222)

    asyncio.run(_runner())

    jm = JobManager()
    jobs = jm.list_jobs(domain=READING_DIGEST_DOMAIN, job_type=READING_DIGEST_JOB_TYPE)
    assert jobs == []
    updated = db.get_reading_digest_schedule(schedule_id)
    assert updated.enabled is False
    assert updated.last_status == "skipped_disabled"
