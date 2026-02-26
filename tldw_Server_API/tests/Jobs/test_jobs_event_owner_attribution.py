import os
import sqlite3

import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.unit


def _setup_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))
    monkeypatch.setenv("JOBS_EVENTS_OUTBOX", "true")


def _latest_owner_for_event(*, db_path, job_id: int, event_type: str) -> str | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT owner_user_id FROM job_events WHERE job_id = ? AND event_type = ? ORDER BY id DESC LIMIT 1",
            (int(job_id), event_type),
        ).fetchone()
    if not row:
        return None
    return row[0]


def test_job_completed_event_includes_owner_user_id(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    jm = JobManager()
    job = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="42",
    )
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=15, worker_id="w1")
    assert acq is not None
    ok = jm.complete_job(
        int(acq["id"]),
        worker_id=acq["worker_id"],
        lease_id=acq["lease_id"],
    )
    assert ok

    owner = _latest_owner_for_event(
        db_path=tmp_path / "Databases" / "jobs.db",
        job_id=int(job["id"]),
        event_type="job.completed",
    )
    assert owner == "42"


def test_job_failed_event_includes_owner_user_id(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)
    jm = JobManager()
    job = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="77",
    )
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=15, worker_id="w2")
    assert acq is not None
    ok = jm.fail_job(
        int(acq["id"]),
        error="boom",
        retryable=False,
        worker_id=acq["worker_id"],
        lease_id=acq["lease_id"],
    )
    assert ok

    owner = _latest_owner_for_event(
        db_path=tmp_path / "Databases" / "jobs.db",
        job_id=int(job["id"]),
        event_type="job.failed",
    )
    assert owner == "77"
