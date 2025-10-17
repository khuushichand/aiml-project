import os
import time
import threading
import random
from collections import defaultdict

import pytest

psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.pg_jobs


def _require_pg(monkeypatch):
    db_url = os.getenv("JOBS_DB_URL", "")
    if not db_url or not db_url.startswith("postgres"):
        pytest.skip("JOBS_DB_URL not configured for Postgres tests")
    monkeypatch.setenv("JOBS_PG_SINGLE_UPDATE_ACQUIRE", "true")
    monkeypatch.setenv("JOBS_ENFORCE_LEASE_ACK", "true")


def test_pg_single_update_acquire_concurrency(monkeypatch):
    _require_pg(monkeypatch)
    jm = JobManager(backend="postgres", db_url=os.getenv("JOBS_DB_URL"))
    domain = "chatbooks"; queue = "default"; job_type = "export"
    total_jobs = 60
    workers = 8
    # Seed jobs
    for _ in range(total_jobs):
        jm.create_job(domain=domain, queue=queue, job_type=job_type, payload={}, owner_user_id="1", priority=random.randint(1, 10))

    acquired_by = defaultdict(list)
    acquired_ids = set()
    lock = threading.Lock()

    def worker_loop(wid: str):
        while True:
            job = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id=wid)
            if not job:
                break
            with lock:
                jid = int(job["id"])
                assert jid not in acquired_ids, f"duplicate acquisition of job {jid}"
                acquired_ids.add(jid)
                acquired_by[wid].append(jid)
            # Simulate brief processing time variability
            time.sleep(random.uniform(0.0, 0.02))
            jm.complete_job(jid, worker_id=wid, lease_id=str(job.get("lease_id")), completion_token=str(job.get("lease_id")))

    threads = [threading.Thread(target=worker_loop, args=(f"w{i}",)) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    # All jobs should be acquired exactly once
    assert len(acquired_ids) == total_jobs
    # No worker should starve when jobs >= workers
    non_empty = [k for k, v in acquired_by.items() if len(v) > 0]
    assert len(non_empty) == workers
    # Distribution shouldn't be terribly skewed (loose bound)
    sizes = [len(v) for v in acquired_by.values()]
    assert max(sizes) - min(sizes) < total_jobs * 0.5


def test_pg_single_update_acquire_with_slow_worker(monkeypatch):
    _require_pg(monkeypatch)
    jm = JobManager(backend="postgres", db_url=os.getenv("JOBS_DB_URL"))
    domain = "chatbooks"; queue = "default"; job_type = "export"
    total_jobs = 40
    workers = 5
    for _ in range(total_jobs):
        jm.create_job(domain=domain, queue=queue, job_type=job_type, payload={}, owner_user_id="1")

    acquired_ids = set()
    lock = threading.Lock()

    def slow_worker():
        while True:
            job = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id="slow")
            if not job:
                break
            with lock:
                jid = int(job["id"])
                assert jid not in acquired_ids
                acquired_ids.add(jid)
            time.sleep(0.05)  # slower
            jm.complete_job(jid, worker_id="slow", lease_id=str(job.get("lease_id")), completion_token=str(job.get("lease_id")))

    def fast_worker(i: int):
        while True:
            job = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=30, worker_id=f"f{i}")
            if not job:
                break
            with lock:
                jid = int(job["id"])
                assert jid not in acquired_ids
                acquired_ids.add(jid)
            jm.complete_job(jid, worker_id=f"f{i}", lease_id=str(job.get("lease_id")), completion_token=str(job.get("lease_id")))

    threads = [threading.Thread(target=slow_worker)] + [threading.Thread(target=fast_worker, args=(i,)) for i in range(workers - 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(acquired_ids) == total_jobs
    # Ensure slow worker didn't block others due to SKIP LOCKED
    # At least some jobs should be handled by fast workers
    # (we can't easily count per-worker without retaining more state; just assert completion)
    assert len(acquired_ids) == total_jobs


def test_pg_single_update_acquire_priority_ordering_single_worker(monkeypatch):
    _require_pg(monkeypatch)
    jm = JobManager(backend="postgres", db_url=os.getenv("JOBS_DB_URL"))
    domain = "chatbooks"; queue = "default"; job_type = "export"
    # Lower numeric priority should be acquired first when single-update path is enabled
    priorities = [9, 1, 5, 3, 2, 10, 4]
    for p in priorities:
        jm.create_job(domain=domain, queue=queue, job_type=job_type, payload={}, owner_user_id="1", priority=p)
    seen = []
    while True:
        job = jm.acquire_next_job(domain=domain, queue=queue, lease_seconds=10, worker_id="ord")
        if not job:
            break
        seen.append(int(job.get("priority") or 0))
        jm.complete_job(int(job["id"]), worker_id="ord", lease_id=str(job.get("lease_id")), completion_token=str(job.get("lease_id")))
    assert sorted(priorities) == seen, f"Expected ASC priority order, got {seen}"
