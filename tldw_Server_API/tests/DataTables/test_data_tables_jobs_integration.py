import asyncio
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints.data_tables import router as data_tables_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Data_Tables import jobs_worker
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK


pytestmark = pytest.mark.integration


class _StubAdapter:
    def __init__(self, payload):
        self._payload = payload

    def chat(self, _request):
        return {"choices": [{"message": {"content": json.dumps(self._payload)}}]}


def _principal_override():
    async def _override(request=None) -> AuthPrincipal:
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="test-user",
            token_type="single_user",
            jti=None,
            roles=["admin"],
            permissions=["media.create", "media.read", "media.update", "media.delete"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            request.state.auth = AuthContext(
                principal=principal,
                ip=None,
                user_agent=None,
                request_id=None,
            )
        return principal

    return _override


def _build_app(db_path: Path, monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    jobs_db_path = db_path.parent / "jobs.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(jobs_db_path))

    app = FastAPI()
    app.include_router(data_tables_router, prefix="/api/v1", tags=["data-tables"])

    async def _override_user() -> User:
        return User(id=1, username="tester", email=None, is_active=True, is_admin=True)

    async def _override_db():
        override_db = MediaDatabase(db_path=str(db_path), client_id="test_client")
        try:
            yield override_db
        finally:
            override_db.close_connection()

    app.dependency_overrides[get_request_user] = _override_user
    app.dependency_overrides[get_auth_principal] = _principal_override()
    app.dependency_overrides[get_media_db_for_user] = _override_db
    return app, jobs_db_path


def _configure_worker_paths(tmp_path: Path, monkeypatch) -> Path:
    media_path = tmp_path / "media.db"
    chacha_path = tmp_path / "chacha.db"
    monkeypatch.setattr(jobs_worker, "get_user_media_db_path", lambda _user_id: str(media_path))
    monkeypatch.setattr(jobs_worker, "get_user_chacha_db_path", lambda _user_id: str(chacha_path))
    jobs_worker._MEDIA_DB_CACHE.clear()
    jobs_worker._CHACHA_DB_CACHE.clear()
    return media_path


def _stub_llm(monkeypatch, payload):
    monkeypatch.setattr(jobs_worker, "_get_adapter", lambda _provider: _StubAdapter(payload))
    monkeypatch.setattr(jobs_worker, "_resolve_model", lambda *_args, **_kwargs: "test-model")
    monkeypatch.setattr(jobs_worker, "provider_requires_api_key", lambda _p: False)
    monkeypatch.setattr(jobs_worker, "resolve_provider_api_key", lambda *_a, **_k: ("", {}))
    monkeypatch.setattr(jobs_worker, "DEFAULT_LLM_PROVIDER", "openai")
    monkeypatch.setattr(jobs_worker, "load_and_log_configs", lambda: {})


async def _run_worker_once(jm: JobManager):
    cfg = WorkerConfig(
        domain="data_tables",
        queue="default",
        worker_id="worker-test",
        lease_seconds=5,
        renew_threshold_seconds=1,
        renew_jitter_seconds=0,
    )
    sdk = WorkerSDK(jm, cfg)

    async def handler(job_row):
        result = await jobs_worker._handle_job(job_row)
        sdk.stop()
        return result

    await asyncio.wait_for(sdk.run(handler=handler), timeout=2)


@pytest.mark.asyncio
async def test_data_tables_job_lifecycle(monkeypatch, tmp_path):
    media_path = _configure_worker_paths(tmp_path, monkeypatch)
    app, jobs_db_path = _build_app(media_path, monkeypatch)

    llm_payload = {
        "columns": [
            {"name": "Term", "type": "text"},
            {"name": "Count", "type": "number"},
        ],
        "rows": [["alpha", 1], ["beta", 2]],
    }
    _stub_llm(monkeypatch, llm_payload)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/data-tables/generate",
            json={
                "name": "Lifecycle Table",
                "prompt": "Summarize",
                "description": "demo",
                "sources": [
                    {
                        "source_type": "rag_query",
                        "source_id": "summarize",
                        "snapshot": {"chunks": [{"chunk_text": "alpha beta"}]},
                    }
                ],
                "column_hints": [{"name": "Term", "type": "text"}],
            },
        )
        assert resp.status_code == 202, resp.text
        payload = resp.json()
        job_id = payload["job_id"]
        table_uuid = payload["table"]["uuid"]

    jm = JobManager(Path(jobs_db_path))
    await _run_worker_once(jm)

    job_row = jm.get_job(int(job_id))
    assert job_row["status"] == "completed"

    db = MediaDatabase(db_path=str(media_path), client_id="test_client")
    try:
        table_row = db.get_data_table_by_uuid(table_uuid)
        assert table_row["status"] == "ready"
        assert table_row["row_count"] == 2
    finally:
        db.close_connection()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_data_tables_job_cancel(monkeypatch, tmp_path):
    media_path = _configure_worker_paths(tmp_path, monkeypatch)
    app, jobs_db_path = _build_app(media_path, monkeypatch)

    llm_payload = {
        "columns": [{"name": "Term", "type": "text"}],
        "rows": [["alpha"]],
    }
    _stub_llm(monkeypatch, llm_payload)

    def _cancel_on_check(jm, job_id):
        jm.cancel_job(int(job_id), reason="test")
        return True

    monkeypatch.setattr(jobs_worker, "_is_job_cancelled", _cancel_on_check)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/data-tables/generate",
            json={
                "name": "Cancel Table",
                "prompt": "Summarize",
                "sources": [
                    {
                        "source_type": "rag_query",
                        "source_id": "cancel",
                        "snapshot": {"chunks": [{"chunk_text": "alpha beta"}]},
                    }
                ],
            },
        )
        assert resp.status_code == 202, resp.text
        payload = resp.json()
        job_id = payload["job_id"]
        table_uuid = payload["table"]["uuid"]

    jm = JobManager(Path(jobs_db_path))
    await _run_worker_once(jm)

    job_row = jm.get_job(int(job_id))
    assert job_row["status"] == "cancelled"

    db = MediaDatabase(db_path=str(media_path), client_id="test_client")
    try:
        table_row = db.get_data_table_by_uuid(table_uuid)
        assert table_row["status"] == "cancelled"
    finally:
        db.close_connection()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_data_tables_regenerate_uses_snapshot(monkeypatch, tmp_path):
    media_path = _configure_worker_paths(tmp_path, monkeypatch)
    app, jobs_db_path = _build_app(media_path, monkeypatch)

    llm_payload = {
        "columns": [
            {"name": "Term", "type": "text"},
            {"name": "Count", "type": "number"},
        ],
        "rows": [["alpha", 1], ["beta", 2]],
    }
    _stub_llm(monkeypatch, llm_payload)

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/data-tables/generate",
            json={
                "name": "Regen Table",
                "prompt": "Summarize",
                "sources": [
                    {
                        "source_type": "rag_query",
                        "source_id": "regen",
                        "snapshot": {"chunks": [{"chunk_text": "alpha beta"}]},
                    }
                ],
            },
        )
        assert resp.status_code == 202, resp.text
        payload = resp.json()
        table_uuid = payload["table"]["uuid"]

    jm = JobManager(Path(jobs_db_path))
    await _run_worker_once(jm)

    async def _fail_rag(*_args, **_kwargs):
        raise AssertionError("rag_query should not be resolved during regenerate")

    monkeypatch.setattr(jobs_worker, "_resolve_rag_query_source", _fail_rag)

    with TestClient(app) as client:
        regen = client.post(f"/api/v1/data-tables/{table_uuid}/regenerate", json={})
        assert regen.status_code == 202, regen.text
        regen_job_id = regen.json()["job_id"]

    await _run_worker_once(jm)

    regen_job = jm.get_job(int(regen_job_id))
    assert regen_job["status"] == "completed"

    db = MediaDatabase(db_path=str(media_path), client_id="test_client")
    try:
        table_row = db.get_data_table_by_uuid(table_uuid)
        assert table_row["status"] == "ready"
        assert table_row["row_count"] == 2
    finally:
        db.close_connection()
        app.dependency_overrides.clear()
