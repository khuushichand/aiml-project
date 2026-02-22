import asyncio
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.files import router as files_router
from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.initialize import ensure_single_user_rbac_seed_if_needed
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Users_DB import ensure_user_directories, reset_users_db
from tldw_Server_API.app.core.File_Artifacts import jobs_worker
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.integration


def _build_app(monkeypatch, base_dir: Path, jobs_db_path: Path, users_db_path: Path) -> FastAPI:
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("JOBS_DB_PATH", str(jobs_db_path))
    monkeypatch.setenv("FILES_JOBS_QUEUE", "default")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "321")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{users_db_path}")

    app = FastAPI()
    app.include_router(files_router, prefix="/api/v1", tags=["files"])

    async def _override_user() -> User:
        return User(id=321, username="tester", email=None, is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = _override_user
    return app


async def _run_worker_once(jm: JobManager) -> None:
    cfg = WorkerConfig(
        domain=jobs_worker.FILES_DOMAIN,
        queue=os.getenv("FILES_JOBS_QUEUE", "default"),
        worker_id="files-worker-test",
        lease_seconds=5,
        renew_threshold_seconds=1,
        renew_jitter_seconds=0,
    )
    sdk = WorkerSDK(jm, cfg)
    handler_error: Exception | None = None

    async def handler(job_row):
        nonlocal handler_error
        try:
            return await jobs_worker._handle_export_job(job_row)
        except Exception as exc:  # pragma: no cover - exercised in failure mode
            handler_error = exc
            raise
        finally:
            sdk.stop()

    await asyncio.wait_for(sdk.run(handler=handler), timeout=2)
    if handler_error is not None:
        raise AssertionError(f"files worker failed: {handler_error}") from handler_error


@pytest.mark.asyncio
async def test_file_artifacts_async_export_job(monkeypatch, tmp_path):
    base_dir = tmp_path / "user_dbs_files_jobs"
    base_dir.mkdir(parents=True, exist_ok=True)
    jobs_db_path = tmp_path / "jobs.db"
    users_db_path = tmp_path / "users.db"
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    app = None
    try:
        app = _build_app(monkeypatch, base_dir, jobs_db_path, users_db_path)
        # Ensure the single-user seed creates a real user row with id=321 in the test users DB.
        await reset_db_pool()
        await reset_users_db()
        await ensure_single_user_rbac_seed_if_needed()
        await ensure_user_directories(321)
        with TestClient(app) as client:
            payload = {
                "file_type": "data_table",
                "title": "Roster",
                "payload": {"columns": ["Name", "Score"], "rows": [["Ada", 95]]},
                "export": {"format": "csv", "mode": "url", "async_mode": "async"},
                "options": {"persist": True},
            }
            response = client.post("/api/v1/files/create", json=payload)
            assert response.status_code == 202, response.text
            artifact = response.json()["artifact"]
            assert artifact["export"]["status"] == "pending"
            job_id = artifact["export"]["job_id"]
            assert job_id
            file_id = artifact["file_id"]

        jm = JobManager(Path(jobs_db_path))
        await _run_worker_once(jm)

        job_row = jm.get_job(int(job_id))
        assert job_row["status"] == "completed"

        cdb = CollectionsDatabase.for_user(user_id=321)
        row = cdb.get_file_artifact(file_id)
        assert row.export_status == "ready"
        assert row.export_storage_path
        export_path = DatabasePaths.get_user_temp_outputs_dir(321) / row.export_storage_path
        assert export_path.exists()
    finally:
        try:
            await reset_db_pool()
            await reset_users_db()
        except Exception:
            _ = None
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                _ = None
        if app is not None:
            app.dependency_overrides.clear()
