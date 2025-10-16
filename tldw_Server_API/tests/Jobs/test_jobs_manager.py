import os
import tempfile
from datetime import datetime, timedelta

import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.fixture()
def jobs_db(tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    yield db_path


def test_create_and_acquire_and_complete(jobs_db):
    jm = JobManager(jobs_db)
    job = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export", "chatbooks_job_id": "abc"},
        owner_user_id="1",
    )
    assert job["status"] == "queued"

    nextj = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert nextj is not None
    assert nextj["status"] == "processing"
    ok = jm.renew_job_lease(int(nextj["id"]), seconds=30)
    assert ok
    ok2 = jm.complete_job(int(nextj["id"]))
    assert ok2
    got = jm.get_job(int(nextj["id"]))
    assert got["status"] == "completed"


def test_retryable_fail_and_backoff(jobs_db):
    jm = JobManager(jobs_db)
    job = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="import",
        payload={"action": "import", "chatbooks_job_id": "xyz"},
        owner_user_id="1",
        max_retries=2,
    )
    j = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w2")
    assert j is not None
    # Retryable fail schedules back to queued
    ok = jm.fail_job(int(j["id"]), error="boom", retryable=True, backoff_seconds=1)
    assert ok
    j2 = jm.get_job(int(j["id"]))
    assert j2["status"] in ("queued", "failed")
    if j2["status"] == "queued":
        assert j2["retry_count"] >= 1


def test_cancel_paths(jobs_db):
    jm = JobManager(jobs_db)
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    # cancel queued
    ok = jm.cancel_job(int(j1["id"]))
    assert ok
    j1r = jm.get_job(int(j1["id"]))
    assert j1r["status"] == "cancelled"

    # cancel request on processing
    j2 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w3")
    assert acq is not None
    ok2 = jm.cancel_job(int(acq["id"]))
    assert ok2
    j2r = jm.get_job(int(acq["id"]))
    # either processing with cancel_requested_at set, or cancelled if race
    assert j2r["status"] in ("processing", "cancelled")
    if j2r["status"] == "processing":
        assert j2r.get("cancel_requested_at") is not None


def test_idempotency_key_returns_existing(jobs_db):
    jm = JobManager(jobs_db)
    idem_key = "cb-export-uniq-key"
    j1 = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export"},
        owner_user_id="1",
        idempotency_key=idem_key,
    )
    assert j1["status"] == "queued"
    # Second create with same idempotency key should return the same row
    j2 = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export"},
        owner_user_id="1",
        idempotency_key=idem_key,
    )
    assert int(j2["id"]) == int(j1["id"])  # idempotent
    assert j2["status"] == "queued"


def test_available_at_scheduling_delays_acquire(jobs_db):
    jm = JobManager(jobs_db)
    future = datetime.utcnow() + timedelta(seconds=1)
    jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export"},
        owner_user_id="1",
        available_at=future,
    )
    # Should not acquire before available_at
    j = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w4")
    assert j is None
    # Wait for availability window
    import time as _t
    _t.sleep(1.2)
    j2 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w4")
    assert j2 is not None
    assert j2["status"] == "processing"
