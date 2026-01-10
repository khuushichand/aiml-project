import threading
import time
import pytest


pytestmark = pytest.mark.integration


def _make_jobs(db, count=3):
    jobs = []
    for i in range(count):
        job = db.create_job(
            job_type="optimization",
            entity_id=0,
            payload={"n": i},
            priority=10 - i,  # ensure descending priority
        )
        jobs.append(job)
    return jobs


def test_pg_advisory_concurrent_acquire_returns_distinct(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db
    if label != "postgres":
        pytest.skip("Postgres-specific test")

    _make_jobs(db, count=3)

    results = []

    def worker(out_list):
        job = db.acquire_next_job()
        out_list.append(job)

    t1 = threading.Thread(target=worker, args=(results,))
    t2 = threading.Thread(target=worker, args=(results,))
    t1.start(); t2.start(); t1.join(); t2.join()

    assert len(results) == 2
    assert all(r is not None for r in results)
    ids = {r["id"] for r in results}
    assert len(ids) == 2, f"duplicate acquire detected: {results}"


def test_pg_advisory_locked_high_priority_is_skipped(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db
    if label != "postgres":
        pytest.skip("Postgres-specific test")

    jobs = _make_jobs(db, count=2)
    j1, j2 = jobs[0], jobs[1]

    # Lock the highest priority job (j1) to force acquire to pick j2
    with db.backend.transaction() as conn:  # type: ignore[attr-defined]
        # Use %s placeholder for psycopg
        db.backend.execute("SELECT pg_advisory_lock(%s)", (j1["id"],), connection=conn)  # type: ignore[attr-defined]
        try:
            picked = db.acquire_next_job()
            assert picked is not None
            assert picked["id"] == j2["id"], f"expected to pick j2 when j1 is locked, got {picked}"
        finally:
            db.backend.execute("SELECT pg_advisory_unlock(%s)", (j1["id"],), connection=conn)  # type: ignore[attr-defined]


def test_pg_advisory_unlocks_on_terminal_status(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db
    if label != "postgres":
        pytest.skip("Postgres-specific test")

    jobs = _make_jobs(db, count=1)
    job = jobs[0]

    # Transition to processing (acquire) then mark completed
    picked = db.acquire_next_job()
    assert picked and picked["id"] == job["id"] and picked["status"] == "processing"
    # Mark completed, which should attempt advisory unlock
    db.update_job_status(job["id"], "completed")

    # Verify try_advisory_lock succeeds (i.e., not held)
    with db.backend.transaction() as conn:  # type: ignore[attr-defined]
        res = db.backend.execute("SELECT pg_try_advisory_lock(%s)", (job["id"],), connection=conn)  # type: ignore[attr-defined]
        row = res.first
        # psycopg returns dict_row; value under ?column?
        locked = list(row.values())[0] if isinstance(row, dict) else row[0]
        assert locked in (True, 1), f"expected advisory lock to be free, got {row}"
        # Clean up if needed
        db.backend.execute("SELECT pg_advisory_unlock(%s)", (job["id"],), connection=conn)  # type: ignore[attr-defined]


def test_pg_advisory_unlocks_on_retry(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db
    if label != "postgres":
        pytest.skip("Postgres-specific test")

    jobs = _make_jobs(db, count=1)
    job = jobs[0]
    picked = db.acquire_next_job()
    assert picked and picked["id"] == job["id"] and picked["status"] == "processing"

    # Simulate retry; implementation attempts advisory unlock when rescheduling
    ok = db.retry_job_record(job["id"])
    assert ok

    # Verify advisory lock is free
    with db.backend.transaction() as conn:  # type: ignore[attr-defined]
        res = db.backend.execute("SELECT pg_try_advisory_lock(%s)", (job["id"],), connection=conn)  # type: ignore[attr-defined]
        row = res.first
        locked = list(row.values())[0] if isinstance(row, dict) else row[0]
        assert locked in (True, 1), f"expected advisory lock to be free after retry, got {row}"
        db.backend.execute("SELECT pg_advisory_unlock(%s)", (job["id"],), connection=conn)  # type: ignore[attr-defined]
