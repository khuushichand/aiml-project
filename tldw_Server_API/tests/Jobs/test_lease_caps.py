import os
from datetime import datetime
import time

import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


def _parse_sqlite_ts(s: str) -> datetime:
    # SQLite DATETIME('now') returns 'YYYY-MM-DD HH:MM:SS'
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.fromisoformat(s)


def test_lease_cap_applies_to_acquire_and_renew(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)

    # Set max lease to 2 seconds
    monkeypatch.setenv("JOBS_LEASE_MAX_SECONDS", "2")

    j = jm.create_job(
        domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1"
    )
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=50, worker_id="w1")
    assert acq is not None
    # Inspect leased_until
    row = jm.get_job(int(acq["id"]))
    lu = row.get("leased_until")
    assert lu is not None
    if isinstance(lu, str):
        dt = _parse_sqlite_ts(lu)
    else:
        dt = lu
    delta = (dt - datetime.utcnow()).total_seconds()
    assert delta <= 3.0  # capped at ~2s plus timing margin

    # Renew with a large value and check cap still applies
    ok = jm.renew_job_lease(int(acq["id"]), seconds=99)
    assert ok
    row2 = jm.get_job(int(acq["id"]))
    lu2 = row2.get("leased_until")
    if isinstance(lu2, str):
        dt2 = _parse_sqlite_ts(lu2)
    else:
        dt2 = lu2
    delta2 = (dt2 - datetime.utcnow()).total_seconds()
    assert delta2 <= 3.0
