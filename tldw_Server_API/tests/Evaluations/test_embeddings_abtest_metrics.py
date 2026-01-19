import pytest

from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import (
    ABTestArm,
    ABTestChunking,
    ABTestQuery,
    ABTestRetrieval,
    EmbeddingsABTestConfig,
)
from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.Evaluations.embeddings_abtest_service import (
    build_collections_vector_only,
    EmbeddingsABTestRunError,
    run_abtest_full,
)
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


class _StubMediaDB:
    def get_media_by_id(self, mid):
        return None


class _DummyChroma:
    def __init__(self, user_id, user_embedding_config):
        pass

    def list_collections(self):
        return []

    def delete_collection(self, collection_name: str):
        return None

    def store_in_chroma(self, **kwargs):
        return None


def _clear_metrics(reg, names):
    for name in names:
        key = reg.normalize_metric_name(name)
        reg.values[key].clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_abtest_build_metrics_emitted_on_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    db = EvaluationsDatabase(str(tmp_path / "evals.db"))
    config = EmbeddingsABTestConfig(
        arms=[ABTestArm(provider="openai", model="text-embedding-3-small")],
        media_ids=[],
        chunking=ABTestChunking(method="sentences", size=200, overlap=20, language="en"),
        retrieval=ABTestRetrieval(k=3, search_mode="vector"),
        queries=[ABTestQuery(text="hello", expected_ids=[1])],
        metric_level="media",
        reuse_existing=False,
    )
    test_id = db.create_abtest(name="metrics-fail", config=config.model_dump(), created_by="tester")

    import tldw_Server_API.app.core.Evaluations.embeddings_abtest_service as service
    monkeypatch.setattr(service, "ChromaDBManager", _DummyChroma)

    async def _fail_embed(*args, **kwargs):
        raise EmbeddingsABTestRunError("embed failed", retryable=True)

    monkeypatch.setattr(service, "_embed_texts", _fail_embed)

    reg = get_metrics_registry()
    _clear_metrics(
        reg,
        [
            "embeddings_abtest_arm_builds_total",
            "embeddings_abtest_arm_build_duration_seconds",
        ],
    )

    with pytest.raises(EmbeddingsABTestRunError):
        await build_collections_vector_only(db, config, test_id, "1", _StubMediaDB())

    builds = list(reg.values.get(reg.normalize_metric_name("embeddings_abtest_arm_builds_total"), []))
    assert any(v.labels.get("status") == "failed" for v in builds)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_abtest_run_metrics_emitted_on_success(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("EMBEDDINGS_ENFORCE_POLICY", "false")

    db = EvaluationsDatabase(str(tmp_path / "evals.db"))
    config = EmbeddingsABTestConfig(
        arms=[ABTestArm(provider="openai", model="text-embedding-3-small")],
        media_ids=[],
        chunking=ABTestChunking(method="sentences", size=200, overlap=20, language="en"),
        retrieval=ABTestRetrieval(k=3, search_mode="vector"),
        queries=[ABTestQuery(text="hello", expected_ids=[1])],
        metric_level="media",
        reuse_existing=False,
    )
    test_id = db.create_abtest(name="metrics-success", config=config.model_dump(), created_by="tester")

    import tldw_Server_API.app.core.Evaluations.embeddings_abtest_service as service

    async def _fake_build(*args, **kwargs):
        return []

    async def _fake_run(*args, **kwargs):
        return {}

    monkeypatch.setattr(service, "build_collections_vector_only", _fake_build)
    monkeypatch.setattr(service, "run_vector_search_and_score", _fake_run)
    monkeypatch.setattr(service, "compute_significance", lambda *args, **kwargs: {})

    reg = get_metrics_registry()
    _clear_metrics(
        reg,
        ["embeddings_abtest_runs_total", "embeddings_abtest_run_duration_seconds"],
    )

    await run_abtest_full(db, config, test_id, "1", _StubMediaDB())

    runs = list(reg.values.get(reg.normalize_metric_name("embeddings_abtest_runs_total"), []))
    assert any(v.labels.get("status") == "completed" for v in runs)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_abtest_run_metrics_emitted_on_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("EMBEDDINGS_ENFORCE_POLICY", "false")

    db = EvaluationsDatabase(str(tmp_path / "evals.db"))
    config = EmbeddingsABTestConfig(
        arms=[ABTestArm(provider="openai", model="text-embedding-3-small")],
        media_ids=[],
        chunking=ABTestChunking(method="sentences", size=200, overlap=20, language="en"),
        retrieval=ABTestRetrieval(k=3, search_mode="vector"),
        queries=[ABTestQuery(text="hello", expected_ids=[1])],
        metric_level="media",
        reuse_existing=False,
    )
    test_id = db.create_abtest(name="metrics-run-fail", config=config.model_dump(), created_by="tester")

    import tldw_Server_API.app.core.Evaluations.embeddings_abtest_service as service

    async def _boom(*args, **kwargs):
        raise EmbeddingsABTestRunError("boom", retryable=True)

    monkeypatch.setattr(service, "build_collections_vector_only", _boom)

    reg = get_metrics_registry()
    _clear_metrics(
        reg,
        ["embeddings_abtest_runs_total", "embeddings_abtest_run_duration_seconds"],
    )

    with pytest.raises(EmbeddingsABTestRunError):
        await run_abtest_full(db, config, test_id, "1", _StubMediaDB())

    runs = list(reg.values.get(reg.normalize_metric_name("embeddings_abtest_runs_total"), []))
    assert any(v.labels.get("status") == "failed" for v in runs)
