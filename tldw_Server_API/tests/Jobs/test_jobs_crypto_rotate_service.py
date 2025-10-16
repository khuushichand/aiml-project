import os
import asyncio

import pytest

from tldw_Server_API.app.services.jobs_crypto_rotate_service import run_jobs_crypto_rotate


@pytest.mark.asyncio
async def test_jobs_crypto_rotate_worker_invokes_rotate(monkeypatch, tmp_path):
    # Point SQLite DB to a temp path so JobManager init doesn't touch repo files
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(str(tmp_path), "jobs.db"))
    # Configure rotation keys and tight interval for a quick loop
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_INTERVAL_SEC", "0.05")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_BATCH", "10")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_FIELDS", "payload,result")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_OLD_KEY", "QUJDREVGR0hJSktMTU5PUFFSU1RVVldY")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_NEW_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwQUJD")

    # Count invocations
    calls = {"n": 0}

    from tldw_Server_API.app.core.Jobs import manager as mgr_mod

    async def _run_once_and_stop(stop_event):
        # Helper to run for slightly more than one interval
        t = asyncio.create_task(run_jobs_crypto_rotate(stop_event))
        await asyncio.sleep(0.12)
        stop_event.set()
        try:
            await asyncio.wait_for(t, timeout=2.0)
        except asyncio.TimeoutError:
            t.cancel()
            raise

    def fake_rotate(self, *, domain=None, queue=None, job_type=None, old_key_b64=None, new_key_b64=None, fields=None, limit=1000, dry_run=False):
        calls["n"] += 1
        return 3

    # Monkeypatch the rotate_encryption_keys method on JobManager
    monkeypatch.setattr(mgr_mod.JobManager, "rotate_encryption_keys", fake_rotate, raising=False)

    stop = asyncio.Event()
    await _run_once_and_stop(stop)

    assert calls["n"] >= 1, "rotate_encryption_keys should be invoked at least once by the worker"


@pytest.mark.asyncio
async def test_jobs_crypto_rotate_worker_noop_when_keys_missing(monkeypatch, tmp_path):
    # No keys provided → worker should not invoke rotate_encryption_keys
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(str(tmp_path), "jobs.db"))
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_INTERVAL_SEC", "0.05")
    # Ensure keys are not set
    monkeypatch.delenv("JOBS_CRYPTO_ROTATE_OLD_KEY", raising=False)
    monkeypatch.delenv("JOBS_CRYPTO_ROTATE_NEW_KEY", raising=False)

    calls = {"n": 0}
    from tldw_Server_API.app.core.Jobs import manager as mgr_mod
    def fake_rotate(self, **kwargs):
        calls["n"] += 1
        return 1
    monkeypatch.setattr(mgr_mod.JobManager, "rotate_encryption_keys", fake_rotate, raising=False)

    stop = asyncio.Event()
    t = asyncio.create_task(run_jobs_crypto_rotate(stop))
    await asyncio.sleep(0.12)
    stop.set()
    try:
        await asyncio.wait_for(t, timeout=2.0)
    except asyncio.TimeoutError:
        t.cancel(); raise
    assert calls["n"] == 0, "rotate_encryption_keys should not be invoked when keys are missing"


@pytest.mark.asyncio
async def test_jobs_crypto_rotate_worker_pg_backend_and_invocation(monkeypatch):
    # Ensure the worker constructs JobManager with backend=postgres when JOBS_DB_URL is set
    from tldw_Server_API.app import services as svc_pkg
    from tldw_Server_API.app.services import jobs_crypto_rotate_service as svc

    # Configure PG DSN and keys so the loop invokes rotation
    dsn = "postgresql://user:pass@localhost:5432/testdb"
    monkeypatch.setenv("JOBS_DB_URL", dsn)
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_INTERVAL_SEC", "0.05")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_OLD_KEY", "QUJDREVGR0hJSktMTU5PUFFSU1RVVldY")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_NEW_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwQUJD")
    monkeypatch.setenv("JOBS_CRYPTO_ROTATE_FIELDS", "payload")

    class FakeJM:
        last_backend = None
        last_db_url = None
        calls = 0
        def __init__(self, *args, **kwargs):
            FakeJM.last_backend = kwargs.get("backend")
            FakeJM.last_db_url = kwargs.get("db_url")
        def rotate_encryption_keys(self, **kwargs):
            FakeJM.calls += 1
            return 2

    # Patch the JobManager symbol used inside the service module
    monkeypatch.setattr(svc, "JobManager", FakeJM, raising=False)

    stop = asyncio.Event()
    t = asyncio.create_task(svc.run_jobs_crypto_rotate(stop))
    await asyncio.sleep(0.12)
    stop.set()
    try:
        await asyncio.wait_for(t, timeout=2.0)
    except asyncio.TimeoutError:
        t.cancel(); raise

    assert FakeJM.calls >= 1
    assert FakeJM.last_backend == "postgres"
    assert FakeJM.last_db_url == dsn
