import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.unit


def _load_ingest_jobs_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "media"
        / "ingest_jobs.py"
    )
    spec = importlib.util.spec_from_file_location(
        "tldw_test_ingest_jobs_batch_lookup",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load ingest_jobs module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for model_name in (
        "MediaIngestJobItem",
        "SubmitMediaIngestJobsResponse",
        "MediaIngestJobStatus",
        "CancelMediaIngestJobResponse",
        "CancelMediaIngestBatchResponse",
        "MediaIngestJobListResponse",
    ):
        model_cls = getattr(module, model_name, None)
        if model_cls is not None and hasattr(model_cls, "model_rebuild"):
            model_cls.model_rebuild(_types_namespace=module.__dict__)
    return module


def test_job_manager_list_jobs_filters_by_batch_group(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("JOBS_DB_URL", raising=False)

    jm = JobManager()
    row_a = jm.create_job(
        domain="media_ingest",
        queue="default",
        job_type="media_ingest_item",
        payload={"batch_id": "batch-a", "source": "https://example.com/a"},
        owner_user_id="1",
        batch_group="batch-a",
    )
    row_b = jm.create_job(
        domain="media_ingest",
        queue="default",
        job_type="media_ingest_item",
        payload={"batch_id": "batch-b", "source": "https://example.com/b"},
        owner_user_id="1",
        batch_group="batch-b",
    )

    rows = jm.list_jobs(
        domain="media_ingest",
        owner_user_id="1",
        batch_group="batch-a",
        limit=25,
    )
    ids = {int(item["id"]) for item in rows}
    assert int(row_a["id"]) in ids
    assert int(row_b["id"]) not in ids


def test_media_ingest_list_endpoint_uses_batch_group_filter(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("JOBS_DB_URL", raising=False)

    ingest_jobs_module = _load_ingest_jobs_module()

    class StubJobManager:
        def __init__(self):
            self.calls: list[dict] = []

        def list_jobs(self, **kwargs):
            self.calls.append(dict(kwargs))
            if kwargs.get("batch_group") == "batch-indexed-1":
                return [
                    {
                        "id": 11,
                        "uuid": "uuid-11",
                        "domain": "media_ingest",
                        "status": "queued",
                        "job_type": "media_ingest_item",
                        "owner_user_id": "1",
                        "created_at": "2026-01-01T00:00:00Z",
                        "started_at": None,
                        "completed_at": None,
                        "cancelled_at": None,
                        "cancellation_reason": None,
                        "progress_percent": None,
                        "progress_message": None,
                        "result": None,
                        "error_message": None,
                        "payload": {
                            "batch_id": "batch-indexed-1",
                            "media_type": "audio",
                            "source": "https://example.com/a",
                            "source_kind": "url",
                        },
                    }
                ]
            return []

    app = FastAPI()
    app.include_router(ingest_jobs_module.router, prefix="/api/v1/media")
    stub = StubJobManager()

    async def _override_user():
        return User(
            id=1,
            username="owner",
            email="owner@example.com",
            role="user",
            is_active=True,
            is_superuser=False,
            is_admin=False,
        )

    async def _override_principal():
        return AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="user:1",
            token_type="access",
            jti=None,
            roles=["user"],
            permissions=["media.create"],
            is_admin=False,
            org_ids=[],
            team_ids=[],
        )

    app.dependency_overrides[ingest_jobs_module.get_job_manager] = lambda: stub
    app.dependency_overrides[get_request_user] = _override_user
    app.dependency_overrides[get_auth_principal] = _override_principal
    try:
        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/media/ingest/jobs?batch_id=batch-indexed-1",
                headers={"X-API-KEY": "test-api-key-12345"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    jobs = body.get("jobs", [])
    assert len(jobs) == 1
    assert int(jobs[0]["id"]) == 11
    assert any(call.get("batch_group") == "batch-indexed-1" for call in stub.calls), stub.calls
