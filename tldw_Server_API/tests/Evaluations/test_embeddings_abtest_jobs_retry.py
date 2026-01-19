import json

import pytest

from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import (
    ABTestArm,
    ABTestChunking,
    ABTestQuery,
    ABTestRetrieval,
    EmbeddingsABTestConfig,
)
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.Jobs.manager import JobManager
import tldw_Server_API.app.core.Evaluations.embeddings_abtest_jobs_worker as worker


@pytest.mark.integration
@pytest.mark.asyncio
async def test_abtest_job_retries_then_marks_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "false")
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("EVALUATIONS_TEST_DB_PATH", str(tmp_path / "evals.db"))
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_db"))
    reset_settings()

    config = EmbeddingsABTestConfig(
        arms=[ABTestArm(provider="openai", model="text-embedding-3-small")],
        media_ids=[],
        chunking=ABTestChunking(method="sentences", size=200, overlap=20, language="en"),
        retrieval=ABTestRetrieval(k=3, search_mode="vector"),
        queries=[ABTestQuery(text="hello", expected_ids=[1])],
        metric_level="media",
        reuse_existing=True,
    )

    svc = worker.get_unified_evaluation_service_for_user(1)
    test_id = svc.db.create_abtest(name="retry-test", config=config.model_dump(), created_by="tester")

    async def _boom(*args, **kwargs):
        raise worker.EmbeddingsABTestRunError("boom", retryable=True)

    monkeypatch.setattr(worker, "run_abtest_full", _boom)
    monkeypatch.setattr(worker, "_build_media_db", lambda user_id: None)

    jm = JobManager()
    from tldw_Server_API.app.core.Jobs.manager import JobManager as _JM
    _JM.set_acquire_gate(False)

    jm.create_job(
        domain="evaluations",
        queue="default",
        job_type="embeddings_abtest_run",
        payload={"test_id": test_id, "config": config.model_dump(), "user_id": "1"},
        owner_user_id="1",
        max_retries=1,
    )

    job = jm.acquire_next_job(domain="evaluations", queue="default", lease_seconds=10, worker_id="w1")
    assert job is not None
    with pytest.raises(worker.EmbeddingsABTestRunError) as exc:
        await worker.handle_abtest_job(job)
    jm.fail_job(
        int(job["id"]),
        error=str(exc.value),
        retryable=bool(getattr(exc.value, "retryable", True)),
        backoff_seconds=0,
        worker_id="w1",
        lease_id=str(job.get("lease_id")),
        enforce=False,
    )

    row = svc.db.get_abtest(test_id)
    assert row is not None
    assert row.get("status") != "failed"

    job2 = jm.acquire_next_job(domain="evaluations", queue="default", lease_seconds=10, worker_id="w2")
    assert job2 is not None
    with pytest.raises(worker.EmbeddingsABTestRunError) as exc2:
        await worker.handle_abtest_job(job2)
    jm.fail_job(
        int(job2["id"]),
        error=str(exc2.value),
        retryable=bool(getattr(exc2.value, "retryable", True)),
        backoff_seconds=0,
        worker_id="w2",
        lease_id=str(job2.get("lease_id")),
        enforce=False,
    )

    row2 = svc.db.get_abtest(test_id)
    assert row2 is not None
    assert row2.get("status") == "failed"
    stats = json.loads(row2.get("stats_json") or "{}")
    assert "error" in stats
    reset_settings()
