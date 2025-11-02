import os

from tldw_Server_API.app.core.Jobs.manager import JobManager


def _set_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))


def test_renew_progress_persists_without_enforcement_sqlite(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)

    jm = JobManager()
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert acq and str(acq.get("status")) == "processing"

    ok = jm.renew_job_lease(int(acq["id"]), seconds=10, progress_percent=42.5, progress_message="halfway")
    assert ok is True

    got = jm.get_job(int(acq["id"]))
    assert got.get("status") == "processing"
    assert got.get("progress_percent") == 42.5
    assert got.get("progress_message") == "halfway"


def test_renew_progress_persists_with_enforcement_sqlite(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    monkeypatch.setenv("JOBS_ENFORCE_LEASE_ACK", "true")

    jm = JobManager()
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert acq and str(acq.get("status")) == "processing"

    ok = jm.renew_job_lease(
        int(acq["id"]),
        seconds=10,
        worker_id="w1",
        lease_id=str(acq.get("lease_id")),
        progress_percent=75.0,
        progress_message="3/4",
    )
    assert ok is True

    got = jm.get_job(int(acq["id"]))
    assert got.get("progress_percent") == 75.0
    assert got.get("progress_message") == "3/4"
