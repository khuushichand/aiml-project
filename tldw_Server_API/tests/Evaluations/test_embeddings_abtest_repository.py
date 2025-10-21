from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from tldw_Server_API.app.core.Evaluations.embeddings_abtest_repository import (
    EmbeddingABTestRepository,
    RepositoryConfig,
)


def _make_repo() -> EmbeddingABTestRepository:
    config = RepositoryConfig(db_url="sqlite:///:memory:")
    return EmbeddingABTestRepository.from_config(config)


def test_create_and_fetch_abtest():
    repo = _make_repo()
    test_id = f"test-{uuid4()}"
    repo.create_test(
        test_id=test_id,
        name="baseline-vs-upgrade",
        created_by="tester",
        config={"control": {"provider": "openai", "model": "text-embedding-3-small"}},
    )
    repo.add_arm(
        arm_id=f"arm-{uuid4()}",
        test_id=test_id,
        arm_index=0,
        provider="openai",
        model_id="text-embedding-3-small",
        status="ready",
    )
    repo.add_query(
        query_id=f"query-{uuid4()}",
        test_id=test_id,
        text="quick brown fox",
        ground_truth_ids=["doc-1"],
    )
    repo.record_result(
        result_id=f"result-{uuid4()}",
        test_id=test_id,
        arm_id=repo.get_test_with_children(test_id).arms[0].arm_id,  # type: ignore[union-attr]
        query_id=repo.get_test_with_children(test_id).queries[0].query_id,  # type: ignore[union-attr]
        ranked_ids=["doc-1", "doc-2"],
        scores=[0.9, 0.1],
        metrics={"recall@1": 1.0},
        latency_ms=42.5,
    )
    repo.update_test_status(test_id=test_id, status="completed", stats={"tests_completed": 1})

    snapshot = repo.get_test_with_children(test_id)
    assert snapshot is not None
    assert snapshot.status == "completed"
    assert snapshot.arms and len(snapshot.arms) == 1
    assert snapshot.queries and len(snapshot.queries) == 1
    assert snapshot.results and len(snapshot.results) == 1
    assert snapshot.stats_json is not None


def test_create_test_defaults_timestamp():
    repo = _make_repo()
    test_id = f"test-{uuid4()}"
    entity = repo.create_test(
        test_id=test_id,
        name="default-timestamp",
        created_by=None,
        config={"arms": []},
    )
    assert entity.test_id == test_id
    assert entity.created_at.tzinfo is not None
    assert entity.created_at <= datetime.now(timezone.utc)
