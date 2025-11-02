import os
import pytest


psycopg = pytest.importorskip("psycopg")

from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.pg_jobs


def _require_pg(monkeypatch):
    db_url = os.getenv("JOBS_DB_URL", "")
    if not db_url or not db_url.startswith("postgres"):
        pytest.skip("JOBS_DB_URL not configured for Postgres tests")
    # Enforce lease ack + completion token semantics
    monkeypatch.setenv("JOBS_ENFORCE_LEASE_ACK", "true")
    monkeypatch.setenv("JOBS_REQUIRE_COMPLETION_TOKEN", "true")
    # Ensure single-update acquire path is on for these tests
    monkeypatch.setenv("JOBS_PG_SINGLE_UPDATE_ACQUIRE", "true")


def test_pg_complete_idempotent_with_token(monkeypatch):
    _require_pg(monkeypatch)
    jm = JobManager(backend="postgres", db_url=os.getenv("JOBS_DB_URL"))
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="wp1")
    assert acq and acq["id"] == j["id"]
    token = str(acq.get("lease_id"))
    ok1 = jm.complete_job(int(j["id"]), result={"ok": True}, worker_id="wp1", lease_id=str(acq.get("lease_id")), completion_token=token)
    assert ok1 is True
    ok2 = jm.complete_job(int(j["id"]), result={"ok": True}, worker_id="wp1", lease_id=str(acq.get("lease_id")), completion_token=token)
    assert ok2 is True
    ok3 = jm.complete_job(int(j["id"]), result={"ok": True}, worker_id="wp1", lease_id=str(acq.get("lease_id")), completion_token=token+"-x")
    assert ok3 is False


def test_pg_fail_idempotent_with_token(monkeypatch):
    _require_pg(monkeypatch)
    jm = JobManager(backend="postgres", db_url=os.getenv("JOBS_DB_URL"))
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="wp2")
    assert acq and acq["id"] == j["id"]
    token = str(acq.get("lease_id"))
    ok1 = jm.fail_job(int(j["id"]), error="boom", retryable=False, worker_id="wp2", lease_id=str(acq.get("lease_id")), completion_token=token)
    assert ok1 is True
    ok2 = jm.fail_job(int(j["id"]), error="boom", retryable=False, worker_id="wp2", lease_id=str(acq.get("lease_id")), completion_token=token)
    assert ok2 is True
    ok3 = jm.fail_job(int(j["id"]), error="boom", retryable=False, worker_id="wp2", lease_id=str(acq.get("lease_id")), completion_token=token+"-x")
    assert ok3 is False
