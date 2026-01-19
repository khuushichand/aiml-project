import json

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
)


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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arm_status_failed_on_build_error(tmp_path, monkeypatch):
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
    test_id = db.create_abtest(name="status-fail", config=config.model_dump(), created_by="tester")

    import tldw_Server_API.app.core.Evaluations.embeddings_abtest_service as service

    monkeypatch.setattr(service, "ChromaDBManager", _DummyChroma)

    async def _fail_embed(*args, **kwargs):
        raise EmbeddingsABTestRunError("embed failed", retryable=True)

    monkeypatch.setattr(service, "_embed_texts", _fail_embed)

    with pytest.raises(EmbeddingsABTestRunError):
        await build_collections_vector_only(db, config, test_id, "1", _StubMediaDB())

    arms = db.get_abtest_arms(test_id)
    assert arms
    arm = arms[0]
    assert arm.get("status") == "failed"
    stats_raw = arm.get("stats_json")
    if isinstance(stats_raw, str):
        stats = json.loads(stats_raw or "{}")
    elif isinstance(stats_raw, dict):
        stats = stats_raw
    else:
        stats = {}
    assert "error" in stats
