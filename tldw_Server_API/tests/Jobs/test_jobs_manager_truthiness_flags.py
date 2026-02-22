from __future__ import annotations

import sqlite3

import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables


pytestmark = pytest.mark.unit


@pytest.fixture()
def jobs_db(tmp_path):
    db_path = tmp_path / "jobs_truthy.db"
    ensure_jobs_tables(db_path)
    return db_path


def test_domain_encrypt_flag_accepts_single_letter_y(monkeypatch: pytest.MonkeyPatch, jobs_db) -> None:
    monkeypatch.setenv("JOBS_ENCRYPT", "0")
    monkeypatch.setenv("JOBS_ENCRYPT_SECURE", "y")
    jm = JobManager(jobs_db)
    assert jm._should_encrypt("secure") is True
    assert jm._should_encrypt("other") is False


def test_sqlite_single_update_acquire_flag_accepts_single_letter_y(
    monkeypatch: pytest.MonkeyPatch,
    jobs_db,
) -> None:
    monkeypatch.setenv("JOBS_SQLITE_SINGLE_UPDATE_ACQUIRE", "y")
    jm = JobManager(jobs_db)
    created = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="1",
    )
    acquired = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert acquired is not None
    assert int(acquired["id"]) == int(created["id"])
    assert acquired["status"] == "processing"


def test_counters_enabled_flag_accepts_single_letter_y(monkeypatch: pytest.MonkeyPatch, jobs_db) -> None:
    monkeypatch.setenv("JOBS_COUNTERS_ENABLED", "y")
    jm = JobManager(jobs_db)
    jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="1",
    )

    conn = sqlite3.connect(jobs_db)
    try:
        row = conn.execute(
            "SELECT ready_count, scheduled_count, processing_count FROM job_counters WHERE domain=? AND queue=? AND job_type=?",
            ("chatbooks", "default", "export"),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert int(row[0]) == 1
    assert int(row[1]) == 0
    assert int(row[2]) == 0


def test_require_completion_token_flag_accepts_single_letter_y(
    monkeypatch: pytest.MonkeyPatch,
    jobs_db,
) -> None:
    monkeypatch.setenv("JOBS_REQUIRE_COMPLETION_TOKEN", "y")
    jm = JobManager(jobs_db)
    created = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="1",
    )
    acquired = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w2")
    assert acquired is not None
    assert int(acquired["id"]) == int(created["id"])

    with pytest.raises(ValueError, match="completion_token required"):
        jm.complete_job(int(created["id"]), result={"ok": True}, worker_id="w2", lease_id=str(acquired.get("lease_id")))
