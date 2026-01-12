import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.evaluations_unified import router as evals_router
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
import tldw_Server_API.app.core.Evaluations.embeddings_abtest_jobs_worker as worker


@pytest.mark.integration
@pytest.mark.asyncio
async def test_abtest_run_enqueues_and_worker_handles(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "false")
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("EVALUATIONS_TEST_DB_PATH", str(tmp_path / "evals.db"))
    reset_settings()

    app = FastAPI()
    app.include_router(evals_router, prefix="/api/v1")
    app.dependency_overrides[get_auth_principal] = lambda: AuthPrincipal(
        kind="user",
        user_id=1,
        is_admin=True,
    )

    settings = get_settings()
    headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY, "Content-Type": "application/json"}

    payload = {
        "arms": [{"provider": "openai", "model": "text-embedding-3-small"}],
        "media_ids": [],
        "retrieval": {"k": 3, "search_mode": "vector"},
        "queries": [{"text": "hello"}],
        "metric_level": "media",
    }

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/evaluations/embeddings/abtest",
            json={"name": "jobs-abtest", "config": payload},
            headers=headers,
        )
        assert created.status_code == 200, created.text
        test_id = created.json()["test_id"]

        run_resp = client.post(
            f"/api/v1/evaluations/embeddings/abtest/{test_id}/run",
            json={"config": payload},
            headers=headers,
        )
        assert run_resp.status_code == 200, run_resp.text

    async def _fake_run_abtest_full(db, config, test_id, user_id, media_db):
        db.set_abtest_status(test_id, "completed", stats_json={"progress": {"phase": 1.0}})

    monkeypatch.setattr(worker, "run_abtest_full", _fake_run_abtest_full)

    jm = JobManager()
    job = jm.acquire_next_job(
        domain="evaluations",
        queue="default",
        lease_seconds=30,
        worker_id="test-worker",
    )
    assert job is not None
    result = await worker.handle_abtest_job(job)
    assert result["test_id"] == test_id
    jm.complete_job(int(job["id"]), result=result, worker_id="test-worker", lease_id=str(job.get("lease_id")), enforce=False)

    svc = worker.get_unified_evaluation_service_for_user(1)
    row = svc.db.get_abtest(test_id)
    assert row is not None
    assert row.get("status") == "completed"
    reset_settings()
