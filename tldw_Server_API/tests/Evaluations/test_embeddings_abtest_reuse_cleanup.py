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
    cleanup_abtest_resources,
)


def _make_config(media_ids):
    return EmbeddingsABTestConfig(
        arms=[ABTestArm(provider="openai", model="text-embedding-3-small")],
        media_ids=list(media_ids),
        chunking=ABTestChunking(method="sentences", size=200, overlap=20, language="en"),
        retrieval=ABTestRetrieval(k=3, search_mode="vector"),
        queries=[ABTestQuery(text="hello", expected_ids=[1])],
        metric_level="media",
        reuse_existing=True,
    )


@pytest.mark.unit
def test_collection_hash_deterministic_and_sensitive():
    cfg_a = _make_config([2, 1])
    cfg_b = _make_config([1, 2])
    hash_a = _compute_collection_hash(cfg_a, 0)
    hash_b = _compute_collection_hash(cfg_b, 0)
    assert hash_a == hash_b

    cfg_c = EmbeddingsABTestConfig(
        arms=[ABTestArm(provider="openai", model="text-embedding-3-small")],
        media_ids=[1, 2],
        chunking=ABTestChunking(method="sentences", size=250, overlap=20, language="en"),
        retrieval=ABTestRetrieval(k=3, search_mode="vector"),
        queries=[ABTestQuery(text="hello", expected_ids=[1])],
        metric_level="media",
        reuse_existing=True,
    )
    hash_c = _compute_collection_hash(cfg_c, 0)
    assert hash_a != hash_c


@pytest.mark.unit
def test_cleanup_deletes_db_rows_and_idempotency(tmp_path, monkeypatch):
    db_path = tmp_path / "evals.db"
    db = EvaluationsDatabase(str(db_path))
    config = _make_config([1])
    test_id = db.create_abtest(name="cleanup", config=config.model_dump(), created_by="tester")
    arm_id = db.upsert_abtest_arm(
        test_id=test_id,
        arm_index=0,
        provider="openai",
        model_id="text-embedding-3-small",
        collection_hash="hash1",
        pipeline_hash="pipe1",
        collection_name=f"user_1_abtest_{test_id}_arm_0",
        status="ready",
    )
    qids = db.insert_abtest_queries(test_id, [{"text": "hello", "expected_ids": [1]}])
    db.insert_abtest_result(
        test_id=test_id,
        arm_id=arm_id,
        query_id=qids[0],
        ranked_ids=["1"],
        metrics={"recall_at_k": 1.0},
        latency_ms=12.3,
    )
    db.record_idempotency("emb_abtest_export_json", "idem-1", f"{test_id}:json", "tester")

    deleted = []

    class _DummyChroma:
        def __init__(self, user_id, user_embedding_config):
            pass

        def delete_collection(self, collection_name: str):
            deleted.append(collection_name)

    import tldw_Server_API.app.core.Evaluations.embeddings_abtest_service as service

    monkeypatch.setattr(service, "ChromaDBManager", _DummyChroma)

    result = cleanup_abtest_resources(
        db,
        user_id="1",
        test_id=test_id,
        delete_db=True,
        delete_idempotency=True,
    )
    assert result["collections_deleted"] == 1
    assert deleted == [f"user_1_abtest_{test_id}_arm_0"]
    assert db.get_abtest(test_id) is None
    assert db.lookup_idempotency("emb_abtest_export_json", "idem-1", "tester") is None
