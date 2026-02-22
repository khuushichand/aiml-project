import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.fixture(autouse=True)
def _setup_pg_env(jobs_pg_dsn, monkeypatch):
     # Standardize env per test and avoid DDL races inside JobManager
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("JOBS_DB_URL", jobs_pg_dsn)
    try:
        import tldw_Server_API.app.core.Jobs.manager as _jm
        monkeypatch.setattr(_jm, "ensure_jobs_tables_pg", lambda url: url, raising=False)
    except Exception:
        _ = None
    yield


def _new_pg_manager():


    return JobManager(None, backend="postgres", db_url=os.getenv("JOBS_DB_URL"))


def test_pg_create_acquire_complete_idempotent():


    jm = _new_pg_manager()
    idem = "pg-idem-1"
    j1 = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export", "chatbooks_job_id": "p1"},
        owner_user_id="1",
        idempotency_key=idem,
    )
    j2 = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export", "chatbooks_job_id": "p1"},
        owner_user_id="1",
        idempotency_key=idem,
    )
    assert int(j1["id"]) == int(j2["id"])  # idempotent
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="w1")
    assert acq is not None
    assert acq["status"] == "processing"
    ok = jm.complete_job(int(acq["id"]))
    assert ok


def test_pg_concurrent_acquire_skip_locked():


    jm = _new_pg_manager()
    # Seed 4 jobs
    ids = []
    for i in range(4):
        j = jm.create_job(
            domain="chatbooks",
            queue="default",
            job_type="export",
            payload={"action": "export", "chatbooks_job_id": f"pj{i}"},
            owner_user_id="1",
        )
        ids.append(int(j["id"]))

    def acq_one(tag):

        jmx = _new_pg_manager()
        got = jmx.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id=tag)
        return got["id"] if got else None

    with ThreadPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(acq_one, "wA")
        f2 = ex.submit(acq_one, "wB")
        f3 = ex.submit(acq_one, "wC")
        r1, r2, r3 = f1.result(), f2.result(), f3.result()

    got_ids = {r for r in (r1, r2, r3) if r is not None}
    # Expect at least 2 distinct jobs acquired without conflict
    assert len(got_ids) >= 2


def test_pg_reschedule_persists_updates():


    jm = _new_pg_manager()
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    job = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export"},
        owner_user_id="1",
        available_at=future,
    )
    before = jm.get_job(int(job["id"]))["available_at"]
    count = jm.reschedule_jobs(
        domain="chatbooks",
        queue="default",
        job_type="export",
        status="queued",
        set_now=True,
        dry_run=False,
    )
    assert count >= 1
    after = jm.get_job(int(job["id"]))["available_at"]
    assert after is not None
    assert after < before
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w-resched")
    assert acq and int(acq["id"]) == int(job["id"])
