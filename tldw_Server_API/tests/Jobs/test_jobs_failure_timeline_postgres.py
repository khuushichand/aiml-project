import os
import json
import pytest
from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.pg_jobs


def _pg_env(monkeypatch):
    dsn = os.getenv("JOBS_DB_URL")
    if not dsn:
        pytest.skip("JOBS_DB_URL not set")


def _read_timeline_pg(jm: JobManager, job_id: int):
    conn = jm._connect()
    try:
        with jm._pg_cursor(conn) as cur:
            cur.execute("SELECT failure_timeline FROM jobs WHERE id = %s", (int(job_id),))
            row = cur.fetchone()
        val = row["failure_timeline"] if row else None
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return []
        return []
    finally:
        conn.close()


def test_failure_timeline_append_and_jsonb_postgres(monkeypatch):
    _pg_env(monkeypatch)
    jm = JobManager(backend="postgres", db_url=os.getenv("JOBS_DB_URL"))

    j = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="u", max_retries=50)
    acq = jm.acquire_next_job(domain="d", queue="default", lease_seconds=5, worker_id="w1")
    assert acq

    for i in range(5):
        ok = jm.fail_job(int(acq["id"]), error="boom", error_code="E_PG", retryable=True, backoff_seconds=0)
        assert ok
        acq = jm.acquire_next_job(domain="d", queue="default", lease_seconds=5, worker_id="w1")
        assert acq

    tl = _read_timeline_pg(jm, int(acq["id"]))
    assert isinstance(tl, list)
    assert len(tl) >= 1
    assert all("error_code" in e for e in tl)
