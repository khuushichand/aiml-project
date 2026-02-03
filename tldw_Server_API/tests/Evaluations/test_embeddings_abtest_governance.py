import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.evaluations.evaluations_unified import router as evals_router
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
from tldw_Server_API.app.core.config import settings as app_settings
import tldw_Server_API.app.core.Evaluations.embeddings_abtest_jobs_worker as worker
from tldw_Server_API.app.core.Evaluations.embeddings_abtest_service import EmbeddingsABTestPolicyError
from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
    get_unified_evaluation_service_for_user,
)


@pytest.fixture()
def evals_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "false")
    monkeypatch.setenv("EVALUATIONS_TEST_DB_PATH", str(tmp_path / "evals.db"))
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_db"))
    reset_settings()

    app = FastAPI()
    app.include_router(evals_router, prefix="/api/v1")

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY, "Content-Type": "application/json"}
    client = TestClient(app)
    yield client, headers
    reset_settings()


@pytest.mark.integration
def test_abtest_provider_allowlist_blocks_create(evals_client, monkeypatch):
    client, headers = evals_client
    monkeypatch.setenv("EMBEDDINGS_ENFORCE_POLICY", "true")

    original_allowed_providers = app_settings.get("ALLOWED_EMBEDDING_PROVIDERS")
    original_allowed_models = app_settings.get("ALLOWED_EMBEDDING_MODELS")
    try:
        app_settings["ALLOWED_EMBEDDING_PROVIDERS"] = ["huggingface"]
        app_settings["ALLOWED_EMBEDDING_MODELS"] = ["sentence-transformers/all-MiniLM-L6-v2"]

        payload = {
            "arms": [{"provider": "openai", "model": "text-embedding-3-small"}],
            "media_ids": [],
            "retrieval": {"k": 3, "search_mode": "vector"},
            "queries": [{"text": "hello"}],
            "metric_level": "media",
        }
        r = client.post(
            "/api/v1/evaluations/embeddings/abtest",
            json={"name": "policy-check", "config": payload},
            headers=headers,
        )
        assert r.status_code == 403, r.text
        assert "not allowed" in r.json().get("detail", "").lower()
    finally:
        if original_allowed_providers is None:
            app_settings.pop("ALLOWED_EMBEDDING_PROVIDERS", None)
        else:
            app_settings["ALLOWED_EMBEDDING_PROVIDERS"] = original_allowed_providers
        if original_allowed_models is None:
            app_settings.pop("ALLOWED_EMBEDDING_MODELS", None)
        else:
            app_settings["ALLOWED_EMBEDDING_MODELS"] = original_allowed_models


@pytest.mark.integration
def test_abtest_run_quota_rejected(evals_client, monkeypatch):
    client, headers = evals_client
    monkeypatch.setenv("EVALS_ABTEST_MAX_QUERIES", "1")

    create_payload = {
        "arms": [{"provider": "openai", "model": "text-embedding-3-small"}],
        "media_ids": [],
        "retrieval": {"k": 3, "search_mode": "vector"},
        "queries": [{"text": "hello"}],
        "metric_level": "media",
    }
    created = client.post(
        "/api/v1/evaluations/embeddings/abtest",
        json={"name": "quota-check", "config": create_payload},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    test_id = created.json()["test_id"]

    run_payload = dict(create_payload)
    run_payload["queries"] = [{"text": "hello"}, {"text": "world"}]
    r = client.post(
        f"/api/v1/evaluations/embeddings/abtest/{test_id}/run",
        json={"config": run_payload},
        headers=headers,
    )
    assert r.status_code == 429, r.text
    assert "quota" in r.json().get("detail", "").lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_abtest_worker_quota_blocks_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALS_ABTEST_MAX_ARMS", "1")
    monkeypatch.setenv("EVALUATIONS_TEST_DB_PATH", str(tmp_path / "evals.db"))
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_db"))
    reset_settings()

    svc = get_unified_evaluation_service_for_user(1)
    config = {
        "arms": [
            {"provider": "openai", "model": "text-embedding-3-small"},
            {"provider": "huggingface", "model": "sentence-transformers/all-MiniLM-L6-v2"},
        ],
        "media_ids": [],
        "retrieval": {"k": 3, "search_mode": "vector"},
        "queries": [{"text": "hello"}],
        "metric_level": "media",
    }
    test_id = svc.db.create_abtest(name="quota-worker", config=config, created_by="tester")

    job = {
        "job_type": "embeddings_abtest_run",
        "payload": {"test_id": test_id, "config": config, "user_id": "1"},
        "owner_user_id": "1",
        "retry_count": 0,
        "max_retries": 0,
    }
    with pytest.raises(EmbeddingsABTestPolicyError):
        await worker.handle_abtest_job(job)

    row = svc.db.get_abtest(test_id)
    assert row is not None
    assert row.get("status") == "failed"
    stats = row.get("stats_json")
    if isinstance(stats, str):
        stats = json.loads(stats)
    assert stats.get("policy_type") == "quota"
    reset_settings()
