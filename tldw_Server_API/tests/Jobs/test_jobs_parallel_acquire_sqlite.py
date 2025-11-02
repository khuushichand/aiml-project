import threading
import time
import os

from collections import defaultdict

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


def test_parallel_acquire_no_double_sqlite(tmp_path):
    db_path = tmp_path / "jobs_parallel.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    total = 30
    for i in range(total):
        jm.create_job(domain="ps", queue="default", job_type="t", payload={"i": i}, owner_user_id="u")

    acquired = defaultdict(list)
    stop = threading.Event()

    def worker(name: str):
        local = JobManager(db_path)
        while not stop.is_set():
            j = local.acquire_next_job(domain="ps", queue="default", lease_seconds=10, worker_id=name)
            if not j:
                # brief pause then check again; exit when seemingly drained
                time.sleep(0.01)
                # Simple drain detection: if no jobs after a few loops, stop
                if len([1 for _ in range(5) if not local.acquire_next_job(domain="ps", queue="default", lease_seconds=1, worker_id=name)]) == 5:
                    break
                continue
            acquired[name].append(int(j["id"]))

    threads = [threading.Thread(target=worker, args=(f"T{i}",), daemon=True) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3)
    stop.set()

    # Flatten and ensure uniqueness across all threads
    flat = [jid for lst in acquired.values() for jid in lst]
    assert len(flat) == len(set(flat))
    # At least most of the jobs should be acquired exactly once
    assert len(flat) >= total * 0.7
