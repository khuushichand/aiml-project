import os
import sqlite3
from datetime import datetime

import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


def _parse_sqlite_ts(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.fromisoformat(s)


def test_acquire_with_transient_db_timeout_then_retry_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    jm.create_job(domain="chatbooks", queue="default", job_type="t", payload={}, owner_user_id="u")

    # Patch _connect to raise once to simulate transient timeout/lock
    orig = jm._connect
    called = {"n": 0}

    def flaky_connect():
        if called["n"] == 0:
            called["n"] += 1
            raise sqlite3.OperationalError("database is locked")
        return orig()

    jm._connect = flaky_connect  # type: ignore

    with pytest.raises(sqlite3.OperationalError):
        jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w1")

    # Restore and retry
    jm._connect = orig  # type: ignore
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w1")
    assert acq and str(acq.get("status")) == "processing"


def test_complete_transient_error_then_idempotent_finalize_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs2.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    j = jm.create_job(domain="ps", queue="default", job_type="t", payload={}, owner_user_id="u")
    acq = jm.acquire_next_job(domain="ps", queue="default", lease_seconds=5, worker_id="w1")
    lease_id = str(acq.get("lease_id"))

    # Fail once on complete
    orig = jm._connect
    called = {"n": 0}

    def flaky_connect():
        if called["n"] == 0:
            called["n"] += 1
            raise sqlite3.OperationalError("transient")
        return orig()

    jm._connect = flaky_connect  # type: ignore
    with pytest.raises(sqlite3.OperationalError):
        jm.complete_job(int(acq["id"]), result={"ok": True}, worker_id="w1", lease_id=lease_id, completion_token=lease_id)
    # Restore and finalize
    jm._connect = orig  # type: ignore
    ok = jm.complete_job(int(acq["id"]), result={"ok": True}, worker_id="w1", lease_id=lease_id, completion_token=lease_id)
    assert ok is True
    # Idempotent retry with same token returns True
    ok2 = jm.complete_job(int(acq["id"]), result={"ok": True}, worker_id="w1", lease_id=lease_id, completion_token=lease_id)
    assert ok2 is True


def test_renew_with_clock_skew_does_not_shrink_lease_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs3.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    jm.create_job(domain="ps", queue="default", job_type="t", payload={}, owner_user_id="u")
    acq = jm.acquire_next_job(domain="ps", queue="default", lease_seconds=20, worker_id="w")
    row = jm.get_job(int(acq["id"]))
    before = _parse_sqlite_ts(row["leased_until"]) if isinstance(row["leased_until"], str) else row["leased_until"]

    # Move clock backwards and renew; leased_until should not move back
    # Capture current epoch from manager clock and subtract skew
    from time import time as _now
    skewed = int(_now()) - 3600
    monkeypatch.setenv("JOBS_TEST_NOW_EPOCH", str(skewed))
    ok = jm.renew_job_lease(int(acq["id"]), seconds=5)
    assert ok is True
    row2 = jm.get_job(int(acq["id"]))
    after = _parse_sqlite_ts(row2["leased_until"]) if isinstance(row2["leased_until"], str) else row2["leased_until"]
    assert after >= before
