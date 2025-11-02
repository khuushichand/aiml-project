import threading
import time
import pytest


class _StubMM:
    def __init__(self):
        self.increments = []

    def increment(self, name, value=1, labels=None):
        self.increments.append((name, value, labels or {}))


class _StubPSMetrics:
    def __init__(self):
        self.metrics_manager = _StubMM()


pytestmark = pytest.mark.integration


def _make_jobs(db, count=40):
    for i in range(count):
        db.create_job(job_type="evaluation", entity_id=1000 + i, payload={"i": i})


def test_pg_advisory_lock_stress_threaded(prompt_studio_dual_backend_db, monkeypatch):
    label, db = prompt_studio_dual_backend_db
    if label != "postgres":
        pytest.skip("Postgres-specific stress test")

    # Stub metrics in monitoring so DB path uses it
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import monitoring as mon
    stub = _StubPSMetrics()
    monkeypatch.setattr(mon, "prompt_studio_metrics", stub, raising=True)

    total_jobs = 48
    _make_jobs(db, count=total_jobs)

    acquired = []
    acquired_lock = threading.Lock()

    def worker():
        while True:
            job = db.acquire_next_job()
            if not job:
                break
            with acquired_lock:
                acquired.append(int(job["id"]))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    # Assert no duplicates and full drain
    assert len(acquired) == total_jobs, f"Expected {total_jobs}, got {len(acquired)}"
    assert len(set(acquired)) == total_jobs, "Duplicate acquisition detected under contention"

    # Advisory metrics sanity: attempts/acquired/unlocks should be >= total_jobs
    names = [n for (n, _, _) in stub.metrics_manager.increments]
    assert "prompt_studio.pg_advisory.lock_attempts_total" in names
    assert "prompt_studio.pg_advisory.locks_acquired_total" in names
    assert "prompt_studio.pg_advisory.unlocks_total" in names
    attempts = sum(1 for (n, _, _) in stub.metrics_manager.increments if n == "prompt_studio.pg_advisory.lock_attempts_total")
    acquired_cnt = sum(1 for (n, _, _) in stub.metrics_manager.increments if n == "prompt_studio.pg_advisory.locks_acquired_total")
    unlocks_cnt = sum(1 for (n, _, _) in stub.metrics_manager.increments if n == "prompt_studio.pg_advisory.unlocks_total")
    assert acquired_cnt >= total_jobs
    assert unlocks_cnt >= total_jobs
    assert attempts >= acquired_cnt
