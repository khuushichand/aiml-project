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
    _compute_collection_hash,
    build_collections_vector_only,
    run_vector_search_and_score,
)


class _HybridDoc:
    def __init__(self, doc_id, content, metadata, score):
        self.id = doc_id
        self.content = content
        self.metadata = metadata
        self.score = score


class _HybridResult:
    def __init__(self, documents):
        self.documents = documents


class _DummyCollection:
    def query(self, *, query_embeddings, n_results, include):
        return {
            "ids": [["mid1_ch0"]],
            "metadatas": [[{"media_id": "1"}]],
            "documents": [["doc1"]],
            "distances": [[0.1]],
        }


class _DummyChroma:
    def __init__(self, user_id, user_embedding_config):
        self._collection = _DummyCollection()

    def get_or_create_collection(self, _name):
        return self._collection


class _DummyChromaReuse:
    def __init__(self, user_id, user_embedding_config):
        pass

    def list_collections(self):
        return []

    def delete_collection(self, _name):
        raise AssertionError("delete_collection should not be called during reuse")

    def store_in_chroma(self, **_kwargs):
        raise AssertionError("store_in_chroma should not be called during reuse")


class _StubMediaDB:
    def get_media_by_id(self, _mid):
        return None


class _FailIfChromaInitialized:
    def __init__(self, user_id, user_embedding_config):
        raise AssertionError("ChromaDBManager should not be initialized for hybrid search")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_abtest_hybrid_results_are_recorded(tmp_path, monkeypatch):
    config = EmbeddingsABTestConfig(
        arms=[ABTestArm(provider="openai", model="text-embedding-3-small")],
        media_ids=[1],
        chunking=ABTestChunking(method="sentences", size=200, overlap=20, language="en"),
        retrieval=ABTestRetrieval(k=1, search_mode="hybrid", hybrid_alpha=0.7),
        queries=[ABTestQuery(text="hello", expected_ids=[1])],
        metric_level="media",
        reuse_existing=False,
    )
    db = EvaluationsDatabase(str(tmp_path / "evals.db"))
    test_id = db.create_abtest(name="hybrid", config=config.model_dump(), created_by="tester")
    db.insert_abtest_queries(test_id, [q.model_dump() for q in config.queries])
    arm_id = db.upsert_abtest_arm(
        test_id=test_id,
        arm_index=0,
        provider=config.arms[0].provider,
        model_id=config.arms[0].model,
        dimensions=None,
        collection_name="hybrid_collection",
        status="ready",
    )

    async def _fake_embed(*_args, **_kwargs):
        return [[0.0, 1.0]]

    captured = {}

    async def _fake_unified(*_args, **kwargs):
        captured["include_media_ids"] = kwargs.get("include_media_ids")
        docs = [_HybridDoc("doc1", "content", {"media_id": "1"}, 0.9)]
        return _HybridResult(docs)

    import tldw_Server_API.app.core.Evaluations.embeddings_abtest_service as service
    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as unified_pipeline

    monkeypatch.setattr(service, "_embed_texts", _fake_embed)
    monkeypatch.setattr(service, "ChromaDBManager", _FailIfChromaInitialized)
    monkeypatch.setattr(unified_pipeline, "unified_rag_pipeline", _fake_unified)

    await run_vector_search_and_score(
        db,
        config,
        test_id,
        "1",
        [{"arm_id": arm_id, "collection_name": "hybrid_collection"}],
    )

    rows, total = db.list_abtest_results(test_id, limit=10, offset=0)
    assert total == 1
    assert captured["include_media_ids"] == [1]
    metrics = json.loads(rows[0].get("metrics_json") or "{}")
    assert metrics.get("recall_at_k") == 1.0
    assert rows[0].get("ranked_metadatas") is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_abtest_vector_metrics_use_media_ids(tmp_path, monkeypatch):
    config = EmbeddingsABTestConfig(
        arms=[ABTestArm(provider="openai", model="text-embedding-3-small")],
        media_ids=[1],
        chunking=ABTestChunking(method="sentences", size=200, overlap=20, language="en"),
        retrieval=ABTestRetrieval(k=1, search_mode="vector"),
        queries=[ABTestQuery(text="hello", expected_ids=[1])],
        metric_level="media",
        reuse_existing=False,
    )
    db = EvaluationsDatabase(str(tmp_path / "evals.db"))
    test_id = db.create_abtest(name="vector", config=config.model_dump(), created_by="tester")
    db.insert_abtest_queries(test_id, [q.model_dump() for q in config.queries])
    arm_id = db.upsert_abtest_arm(
        test_id=test_id,
        arm_index=0,
        provider=config.arms[0].provider,
        model_id=config.arms[0].model,
        dimensions=None,
        collection_name="vector_collection",
        status="ready",
    )

    async def _fake_embed(*_args, **_kwargs):
        return [[0.0, 1.0]]

    import tldw_Server_API.app.core.Evaluations.embeddings_abtest_service as service

    monkeypatch.setattr(service, "_embed_texts", _fake_embed)
    monkeypatch.setattr(service, "ChromaDBManager", _DummyChroma)

    await run_vector_search_and_score(
        db,
        config,
        test_id,
        "1",
        [{"arm_id": arm_id, "collection_name": "vector_collection"}],
    )

    rows, total = db.list_abtest_results(test_id, limit=10, offset=0)
    assert total == 1
    metrics = json.loads(rows[0].get("metrics_json") or "{}")
    assert metrics.get("recall_at_k") == 1.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_abtest_reuses_collection_across_tests(tmp_path, monkeypatch):
    config = EmbeddingsABTestConfig(
        arms=[ABTestArm(provider="openai", model="text-embedding-3-small")],
        media_ids=[],
        chunking=ABTestChunking(method="sentences", size=200, overlap=20, language="en"),
        retrieval=ABTestRetrieval(k=1, search_mode="vector"),
        queries=[ABTestQuery(text="hello", expected_ids=[1])],
        metric_level="media",
        reuse_existing=True,
    )
    db = EvaluationsDatabase(str(tmp_path / "evals.db"))
    test_id_1 = db.create_abtest(name="reuse-1", config=config.model_dump(), created_by="tester")
    collection_hash = _compute_collection_hash(config, 0)
    db.upsert_abtest_arm(
        test_id=test_id_1,
        arm_index=0,
        provider=config.arms[0].provider,
        model_id=config.arms[0].model,
        dimensions=None,
        collection_hash=collection_hash,
        collection_name="shared_collection",
        status="ready",
    )
    test_id_2 = db.create_abtest(name="reuse-2", config=config.model_dump(), created_by="tester")

    async def _fail_embed(*_args, **_kwargs):
        raise AssertionError("embed should not be called for reuse")

    import tldw_Server_API.app.core.Evaluations.embeddings_abtest_service as service

    monkeypatch.setattr(service, "_embed_texts", _fail_embed)
    monkeypatch.setattr(service, "_collection_exists", lambda _mgr, name: name == "shared_collection")
    monkeypatch.setattr(service, "ChromaDBManager", _DummyChromaReuse)

    arm_info = await build_collections_vector_only(
        db,
        config,
        test_id_2,
        "1",
        _StubMediaDB(),
    )

    assert arm_info[0]["collection_name"] == "shared_collection"
    arms = db.get_abtest_arms(test_id_2)
    meta = json.loads(arms[0].get("metadata_json") or "{}")
    assert meta.get("shared_origin_test_id") == test_id_1
