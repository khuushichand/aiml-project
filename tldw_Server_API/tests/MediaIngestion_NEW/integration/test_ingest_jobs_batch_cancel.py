import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.integration


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
        "tldw_test_ingest_jobs_batch_cancel",
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
        "MediaIngestJobListResponse",
    ):
        model_cls = getattr(module, model_name, None)
        if model_cls is not None and hasattr(model_cls, "model_rebuild"):
            model_cls.model_rebuild(_types_namespace=module.__dict__)
    return module


@pytest.fixture(scope="module")
def ingest_jobs_module():
    return _load_ingest_jobs_module()


@pytest.fixture()
def test_client(ingest_jobs_module):
    app = FastAPI()
    app.include_router(ingest_jobs_module.router, prefix="/api/v1/media")

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

    app.dependency_overrides[get_request_user] = _override_user
    app.dependency_overrides[get_auth_principal] = _override_principal
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _set_jobs_db(monkeypatch, tmp_path, ingest_jobs_module):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("JOBS_DB_URL", raising=False)
    ingest_jobs_module._job_manager_cache.clear()


def _seed_media_ingest_job(*, owner_user_id: int, batch_id: str, source: str, terminal: bool = False) -> int:
    jm = JobManager()
    row = jm.create_job(
        domain="media_ingest",
        queue="default",
        job_type="media_ingest_item",
        payload={
            "batch_id": batch_id,
            "media_type": "audio",
            "source": source,
            "source_kind": "url",
        },
        owner_user_id=str(owner_user_id),
        priority=5,
        max_retries=3,
    )
    job_id = int(row["id"])
    if terminal:
        assert jm.cancel_job(job_id, reason="seed_terminal")
    return job_id


def test_cancel_batch_ingest_jobs(test_client, ingest_jobs_module, monkeypatch, tmp_path):
    _set_jobs_db(monkeypatch, tmp_path, ingest_jobs_module)
    batch_id = "batch-cancel-owned-001"

    queued_job_a = _seed_media_ingest_job(
        owner_user_id=1,
        batch_id=batch_id,
        source="https://example.com/a.mp3",
    )
    queued_job_b = _seed_media_ingest_job(
        owner_user_id=1,
        batch_id=batch_id,
        source="https://example.com/b.mp3",
    )
    terminal_job = _seed_media_ingest_job(
        owner_user_id=1,
        batch_id=batch_id,
        source="https://example.com/c.mp3",
        terminal=True,
    )

    resp = test_client.post(
        f"/api/v1/media/ingest/jobs/cancel?batch_id={batch_id}&reason=user_requested"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["batch_id"] == batch_id
    assert body["requested"] == 3
    assert body["cancelled"] == 2
    assert body["already_terminal"] == 1

    jm = JobManager()
    for job_id in (queued_job_a, queued_job_b, terminal_job):
        row = jm.get_job(job_id) or {}
        assert row.get("status") == "cancelled"


def test_cancel_batch_ingest_jobs_non_owner_forbidden(
    test_client,
    ingest_jobs_module,
    monkeypatch,
    tmp_path,
):
    _set_jobs_db(monkeypatch, tmp_path, ingest_jobs_module)
    batch_id = "batch-cancel-owned-002"

    queued_job = _seed_media_ingest_job(
        owner_user_id=1,
        batch_id=batch_id,
        source="https://example.com/owner-only.mp3",
    )

    async def _override_other_user():
        return User(
            id=999,
            username="other-user",
            email="other@example.com",
            role="user",
            is_active=True,
            is_superuser=False,
            is_admin=False,
        )

    async def _override_other_principal():
        return AuthPrincipal(
            kind="user",
            user_id=999,
            api_key_id=None,
            subject="user:999",
            token_type="access",
            jti=None,
            roles=["user"],
            permissions=["media.create"],
            is_admin=False,
            org_ids=[],
            team_ids=[],
        )

    test_client.app.dependency_overrides[get_request_user] = _override_other_user
    test_client.app.dependency_overrides[get_auth_principal] = _override_other_principal
    try:
        denied_resp = test_client.post(
            f"/api/v1/media/ingest/jobs/cancel?batch_id={batch_id}",
        )
    finally:
        test_client.app.dependency_overrides.pop(get_request_user, None)
        test_client.app.dependency_overrides.pop(get_auth_principal, None)

    assert denied_resp.status_code == 403, denied_resp.text
    jm = JobManager()
    row = jm.get_job(queued_job) or {}
    assert row.get("status") == "queued"
