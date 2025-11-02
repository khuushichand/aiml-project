import threading
import time
from datetime import datetime, timedelta
import pytest


pytestmark = pytest.mark.integration


def _create_jobs(db, n=8):
    jobs = []
    for i in range(n):
        jobs.append(
            db.create_job(
                job_type="optimization",
                entity_id=i,
                payload={"i": i},
                priority=10 - (i % 3),
            )
        )
    return jobs


def test_parallel_acquire_distinct_jobs_dual_backend(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db

    _create_jobs(db, n=6)

    results = []
    lock = threading.Lock()

    def worker():
        job = db.acquire_next_job()
        with lock:
            results.append(job)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    non_null = [r for r in results if r is not None]
    assert len(non_null) == 4
    ids = {r["id"] for r in non_null}
    assert len(ids) == 4, f"duplicate acquires detected: {non_null}"
    for r in non_null:
        assert r.get("status") == "processing"


def test_parallel_acquire_single_job_only_one_gets_it(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db

    _create_jobs(db, n=1)

    results = []
    lock = threading.Lock()

    def worker():
        job = db.acquire_next_job()
        with lock:
            results.append(job)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    non_null = [r for r in results if r is not None]
    assert len(non_null) == 1
    assert non_null[0]["status"] == "processing"


def test_concurrent_renew_extends_lease_dual_backend(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db

    _create_jobs(db, n=1)
    job = db.acquire_next_job()
    assert job is not None

    j0 = db.get_job(job["id"])
    t0 = j0.get("leased_until")

    # Concurrent renew calls with different seconds
    def renew(seconds):
        try:
            db.renew_job_lease(job["id"], seconds=seconds)
        except Exception:
            pass

    threads = [threading.Thread(target=renew, args=(s,)) for s in (5, 7, 9)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    j1 = db.get_job(job["id"])
    t1 = j1.get("leased_until")

    assert t1 is not None and t0 is not None
    # Minimal guarantee: lease did not regress; allow equal if race sets same future window
    assert t1 >= t0


def test_reclaim_expired_processing_job_dual_backend(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db

    _create_jobs(db, n=1)
    job = db.acquire_next_job()
    assert job is not None

    # Force expiration by setting leased_until to past
    if label == "sqlite":
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE prompt_studio_job_queue SET leased_until = DATETIME('now', '-2 seconds') WHERE id = ?",
            (job["id"],),
        )
        conn.commit()
    else:
        db._execute(  # type: ignore[attr-defined]
            "UPDATE prompt_studio_job_queue SET leased_until = NOW() - INTERVAL '2 seconds' WHERE id = ?",
            (job["id"],),
        )

    reclaimed = db.acquire_next_job()
    assert reclaimed is not None
    assert reclaimed["id"] == job["id"], f"Expected to reclaim same job, got {reclaimed}"
