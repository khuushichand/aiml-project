import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.endpoints import chatbooks as chatbooks_mod


class _DummyConn:
    def execute(self, *_args, **_kwargs):
        return None

    def close(self):
        return None


class _DummyCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)


class FakeDB:
    """Minimal in-memory DB to satisfy ChatbookService job storage during tests."""

    def __init__(self):
        self._export_jobs = {}
        self._import_jobs = {}

    def get_connection(self):
        return _DummyConn()

    def execute_query(self, sql, params=(), commit=False):
        sql_norm = " ".join(str(sql).strip().split()).lower()
        # Create tables: no-op
        if sql_norm.startswith("create table if not exists export_jobs"):
            return _DummyCursor([])
        if sql_norm.startswith("create table if not exists import_jobs"):
            return _DummyCursor([])

        # Upsert export job
        if sql_norm.startswith("insert or replace into export_jobs"):
            (
                job_id, user_id, status, chatbook_name, output_path,
                created_at, started_at, completed_at, error_message,
                progress_percentage, total_items, processed_items,
                file_size_bytes, download_url, expires_at,
            ) = params
            self._export_jobs[job_id] = {
                "job_id": job_id,
                "user_id": user_id,
                "status": status,
                "chatbook_name": chatbook_name,
                "output_path": output_path,
                "created_at": created_at,
                "started_at": started_at,
                "completed_at": completed_at,
                "error_message": error_message,
                "progress_percentage": progress_percentage,
                "total_items": total_items,
                "processed_items": processed_items,
                "file_size_bytes": file_size_bytes,
                "download_url": download_url,
                "expires_at": expires_at,
            }
            return _DummyCursor([])

        # Select export job by id + user
        if sql_norm.startswith("select * from export_jobs where job_id"):
            job_id, user_id = params
            row = self._export_jobs.get(job_id)
            if not row or row.get("user_id") != user_id:
                return _DummyCursor([])
            return _DummyCursor([row])

        # Default: empty
        return _DummyCursor([])


@pytest.fixture()
def client_override(tmp_path):
    # Ensure test mode to avoid global rate limiter
    os.environ["TEST_MODE"] = "true"

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True)

    # Use a single FakeDB instance across requests to persist jobs
    _shared_db = FakeDB()

    def override_db():
        return _shared_db

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[chatbooks_mod.get_chacha_db] = override_db

    # Stub audit logger to avoid strict signature requirements in tests
    class _DummyAudit:
        def log_event(self, *args, **kwargs):
            return None
        def log_security_event(self, *args, **kwargs):
            return None

    chatbooks_mod.audit_logger = _DummyAudit()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.unit
def test_chatbooks_export_sync_persists_job_and_downloads(client_override: TestClient):
    client = client_override
    # Create a minimal sync export with no content
    payload = {
        "name": "Test Export",
        "description": "Test run",
        "content_selections": {},
        "async_mode": False,
    }
    r = client.post("/api/v1/chatbooks/export", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert isinstance(data.get("job_id"), str) and len(data["job_id"]) > 0
    assert data.get("download_url", "").endswith(data["job_id"])  # URL is job-based

    job_id = data["job_id"]

    # Fetch the job and validate completed state and URL
    r2 = client.get(f"/api/v1/chatbooks/export/jobs/{job_id}")
    assert r2.status_code == 200, r2.text
    job = r2.json()
    assert job["status"] == "completed"
    assert job.get("download_url", "").endswith(job_id)

    # Download the archive by job_id
    r3 = client.get(f"/api/v1/chatbooks/download/{job_id}")
    assert r3.status_code == 200, r3.text
    assert r3.headers.get("content-type") == "application/zip"
    assert "attachment; filename=" in r3.headers.get("content-disposition", "")
