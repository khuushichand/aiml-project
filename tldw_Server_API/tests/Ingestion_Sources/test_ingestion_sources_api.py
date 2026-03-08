from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def ingestion_sources_client():
    os.environ.setdefault("TEST_MODE", "true")
    os.environ.setdefault("ROUTES_STABLE_ONLY", "false")
    os.environ["ROUTES_ENABLE"] = "ingestion-sources"
    os.environ.setdefault("AUTH_MODE", "single_user")
    os.environ.setdefault("TESTING", "true")

    from tldw_Server_API.app.api.v1.endpoints import ingestion_sources as ingestion_sources_router
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    from tldw_Server_API.app.main import app

    paths = {route.path for route in app.routes}
    if "/api/v1/ingestion-sources/{source_id}/sync" not in paths:
        app.include_router(ingestion_sources_router.router, prefix="/api/v1", tags=["ingestion-sources"])

    api_key = get_settings().SINGLE_USER_API_KEY
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    client = TestClient(app)
    return client, headers


@pytest.mark.integration
def test_manual_sync_endpoint_enqueues_job(ingestion_sources_client, monkeypatch):
    client, auth_headers = ingestion_sources_client

    import tldw_Server_API.app.api.v1.endpoints.ingestion_sources as ep

    queued_jobs: list[dict[str, object]] = []

    class _FakeTx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakePool:
        def transaction(self):
            return _FakeTx()

    async def _fake_get_db_pool():
        return _FakePool()

    async def _fake_ensure_schema(_db):
        return None

    async def _fake_get_source_by_id(_db, *, source_id, user_id=None):
        return {
            "id": source_id,
            "user_id": 1 if user_id is None else user_id,
            "enabled": True,
        }

    def _fake_enqueue_ingestion_source_job(*, user_id, source_id, job_type="sync", idempotency_key=None, payload=None):
        queued_jobs.append(
            {
                "user_id": user_id,
                "source_id": source_id,
                "job_type": job_type,
                "idempotency_key": idempotency_key,
            }
        )
        return {"id": "job-17", "status": "queued"}

    monkeypatch.setattr(ep, "get_db_pool", _fake_get_db_pool)
    monkeypatch.setattr(ep, "ensure_ingestion_sources_schema", _fake_ensure_schema)
    monkeypatch.setattr(ep, "get_source_by_id", _fake_get_source_by_id)
    monkeypatch.setattr(ep, "enqueue_ingestion_source_job", _fake_enqueue_ingestion_source_job)

    response = client.post(
        "/api/v1/ingestion-sources/17/sync",
        headers=auth_headers,
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["source_id"] == 17
    assert payload["job_id"] == "job-17"
    assert queued_jobs[0]["source_id"] == 17
