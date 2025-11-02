import os
import json
from tldw_Server_API.app.core.Jobs.manager import JobManager


def _env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))


def _read_timeline_sqlite(job_id: int):
    jm = JobManager()
    conn = jm._connect()
    try:
        row = conn.execute("SELECT failure_timeline FROM jobs WHERE id = ?", (int(job_id),)).fetchone()
        raw = row[0] if row else None
        try:
            return json.loads(raw) if raw else []
        except Exception:
            return []
    finally:
        conn.close()


def test_failure_timeline_append_and_cap_sqlite(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    jm = JobManager()

    # Create and acquire a job with generous retries
    j = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="u", max_retries=50)
    acq = jm.acquire_next_job(domain="d", queue="default", lease_seconds=5, worker_id="w1")
    assert acq

    # Perform many retryable failures to grow timeline; with TEST_MODE and backoff=0 these are instant
    for i in range(12):
        ok = jm.fail_job(int(acq["id"]), error="boom", error_code="E1", retryable=True, backoff_seconds=0)
        assert ok
        # Immediately reacquire
        acq = jm.acquire_next_job(domain="d", queue="default", lease_seconds=5, worker_id="w1")
        assert acq

    # Timeline should be capped at last 10
    tl = _read_timeline_sqlite(int(acq["id"]))
    assert isinstance(tl, list)
    assert len(tl) == 10
    assert all("error_code" in e and "retry_backoff" in e for e in tl)

    # Terminal fail appends with backoff=0 and remains capped at 10
    ok2 = jm.fail_job(int(acq["id"]), error="BOOM_FINAL", error_code="E_FINAL", retryable=False)
    assert ok2
    tl2 = _read_timeline_sqlite(int(acq["id"]))
    assert len(tl2) == 10
    assert tl2[-1]["error_code"] in {"E_FINAL", "BOOM_FINAL"}
    assert int(tl2[-1]["retry_backoff"]) == 0
