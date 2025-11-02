import os
from tldw_Server_API.app.core.Jobs.manager import JobManager


def _set_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    # SQLite DB path under test dir
    db_path = os.path.join(os.getcwd(), "Databases", "jobs.db")
    monkeypatch.setenv("JOBS_DB_PATH", db_path)
    monkeypatch.setenv("JOBS_ENFORCE_LEASE_ACK", "true")
    monkeypatch.setenv("JOBS_REQUIRE_COMPLETION_TOKEN", "true")


def test_complete_idempotent_with_token(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    jm = JobManager()
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert acq and acq["id"] == j["id"]
    token = str(acq.get("lease_id"))
    ok1 = jm.complete_job(int(j["id"]), result={"ok": True}, worker_id="w1", lease_id=str(acq.get("lease_id")), completion_token=token)
    assert ok1 is True
    # Repeat with same token: should be idempotent success
    ok2 = jm.complete_job(int(j["id"]), result={"ok": True}, worker_id="w1", lease_id=str(acq.get("lease_id")), completion_token=token)
    assert ok2 is True
    # Different token: should not re-complete (status terminal); returns False
    ok3 = jm.complete_job(int(j["id"]), result={"ok": True}, worker_id="w1", lease_id=str(acq.get("lease_id")), completion_token=token + "-x")
    assert ok3 is False


def test_fail_idempotent_with_token(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    jm = JobManager()
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w2")
    assert acq and acq["id"] == j["id"]
    token = str(acq.get("lease_id"))
    ok1 = jm.fail_job(int(j["id"]), error="boom", retryable=False, worker_id="w2", lease_id=str(acq.get("lease_id")), completion_token=token)
    assert ok1 is True
    # Repeat with same token: idempotent success
    ok2 = jm.fail_job(int(j["id"]), error="boom", retryable=False, worker_id="w2", lease_id=str(acq.get("lease_id")), completion_token=token)
    assert ok2 is True
    # Different token: job is already terminal
    ok3 = jm.fail_job(int(j["id"]), error="boom", retryable=False, worker_id="w2", lease_id=str(acq.get("lease_id")), completion_token=token + "-x")
    assert ok3 is False
