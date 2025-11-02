import os
import json

import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


def _set_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    # Ensure a per-test DB file under CWD/Databases
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))


def test_json_caps_payload_reject_and_truncate_sqlite(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)

    # Keep the payload small limit to force edge behaviors
    monkeypatch.setenv("JOBS_MAX_JSON_BYTES", "128")

    jm = JobManager()

    # 1) Reject when truncate disabled (default)
    payload = {"data": "x" * 300}
    with pytest.raises(ValueError) as ei:
        jm.create_job(
            domain="chatbooks",
            queue="default",
            job_type="export",
            payload=payload,
            owner_user_id="u1",
        )
    assert "Payload too large" in str(ei.value)

    # 2) Truncate when enabled
    monkeypatch.setenv("JOBS_JSON_TRUNCATE", "true")
    j = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload=payload,
        owner_user_id="u1",
    )
    # Normalize via get_job so SQLite JSON text is parsed
    got = jm.get_job(int(j["id"]))
    assert isinstance(got, dict)
    assert isinstance(got.get("payload"), dict)
    assert got["payload"].get("_truncated") is True
    assert got["payload"].get("len_bytes") and got["payload"]["len_bytes"] > 128


def test_json_caps_result_reject_and_truncate_sqlite(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    monkeypatch.setenv("JOBS_MAX_JSON_BYTES", "128")

    jm = JobManager()

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

    # 1) Reject when truncate disabled
    with pytest.raises(ValueError) as ei:
        jm.complete_job(int(acq["id"]), result=big_result)
    assert "Result too large" in str(ei.value)

    # 2) Truncate when enabled
    monkeypatch.setenv("JOBS_JSON_TRUNCATE", "true")
    ok = jm.complete_job(int(acq["id"]), result=big_result)
    assert ok is True

    got = jm.get_job(int(acq["id"]))
    assert got.get("status") == "completed"
    res = got.get("result")
    assert isinstance(res, dict)
    assert res.get("_truncated") is True
    assert res.get("len_bytes") and res["len_bytes"] > 128
