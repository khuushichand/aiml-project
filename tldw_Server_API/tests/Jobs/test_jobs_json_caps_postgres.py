import os

import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.pg_jobs

from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
from tldw_Server_API.app.core.Jobs.manager import JobManager


def test_json_caps_payload_reject_and_truncate_postgres(monkeypatch, jobs_pg_dsn):
    monkeypatch.setenv("JOBS_DB_URL", jobs_pg_dsn)
    # Force small limit
    monkeypatch.setenv("JOBS_MAX_JSON_BYTES", "128")

    ensure_jobs_tables_pg(jobs_pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)

    payload = {"data": "x" * 300}

    # Reject when truncate disabled
    with pytest.raises(ValueError) as ei:
        jm.create_job(
            domain="chatbooks",
            queue="default",
            job_type="export",
            payload=payload,
            owner_user_id="u1",
        )
    assert "Payload too large" in str(ei.value)

    # Enable truncation and create
    monkeypatch.setenv("JOBS_JSON_TRUNCATE", "true")
    j = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload=payload,
        owner_user_id="u1",
    )
    got = jm.get_job(int(j["id"]))
    assert isinstance(got.get("payload"), dict)
    assert got["payload"].get("_truncated") is True
    assert got["payload"].get("len_bytes") and got["payload"]["len_bytes"] > 128


def test_json_caps_result_reject_and_truncate_postgres(monkeypatch, jobs_pg_dsn):
    monkeypatch.setenv("JOBS_DB_URL", jobs_pg_dsn)
    # Force small limit
    monkeypatch.setenv("JOBS_MAX_JSON_BYTES", "128")

    ensure_jobs_tables_pg(jobs_pg_dsn)
    jm = JobManager(None, backend="postgres", db_url=jobs_pg_dsn)

    j = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"ok": True},
        owner_user_id="u1",
    )
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert acq and str(acq.get("status")) == "processing"

    big_result = {"data": "y" * 300}

    # Reject when truncate disabled
    with pytest.raises(ValueError) as ei:
        jm.complete_job(int(acq["id"]), result=big_result)
    assert "Result too large" in str(ei.value)

    # Truncate when enabled
    monkeypatch.setenv("JOBS_JSON_TRUNCATE", "true")
    ok = jm.complete_job(int(acq["id"]), result=big_result)
    assert ok is True

    got = jm.get_job(int(acq["id"]))
    assert got.get("status") == "completed"
    res = got.get("result")
    assert isinstance(res, dict)
    assert res.get("_truncated") is True
    assert res.get("len_bytes") and res["len_bytes"] > 128
