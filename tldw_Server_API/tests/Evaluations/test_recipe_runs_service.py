from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import RunStatus
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_single_user_instance
from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.Evaluations.recipe_runs_service import (
    RECIPE_RUN_REUSE_ENTITY_TYPE,
    RecipeDefinitionNotLaunchableError,
    RecipeRunsService,
)
from tldw_Server_API.app.core.Evaluations.recipes.dataset_snapshot import build_dataset_content_hash


def _inline_dataset() -> list[dict[str, Any]]:
    return [
        {
            "input": "What is 2 + 2?",
            "expected": "4",
            "metadata": {"sample_id": "math-1"},
        },
        {
            "input": "What color is the sky on a clear day?",
            "expected": "blue",
            "metadata": {"sample_id": "sky-1"},
        },
    ]


def _run_config() -> dict[str, Any]:
    return {
        "candidate_model_ids": [
            "openai:gpt-4.1-mini",
            "ollama:llama3.1:8b",
        ],
        "judge_config": {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "temperature": 0.0,
        },
        "prompts": {
            "system": "Grade the candidates carefully.",
            "user": "Prefer grounded and concise answers.",
        },
        "weights": {
            "quality": 0.7,
            "cost": 0.2,
            "latency": 0.1,
        },
        "comparison_mode": "pairwise",
        "source_normalization": {
            "strip_citations": True,
            "normalize_whitespace": True,
        },
        "context_policy": {
            "mode": "recipe_default",
            "allow_missing_context": False,
        },
        "execution_policy": {
            "max_parallel_candidates": 2,
            "capture_raw_judgments": True,
        },
    }


def _service(tmp_path) -> tuple[EvaluationsDatabase, RecipeRunsService, str]:
    db = EvaluationsDatabase(str(tmp_path / "evaluations.db"))
    user_id = get_single_user_instance().id_str
    return db, RecipeRunsService(db=db, user_id=user_id), user_id


def _mark_recipe_run_completed(db: EvaluationsDatabase, run_id: str) -> None:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE evaluation_recipe_runs
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE run_id = ?
            """,
            (RunStatus.COMPLETED.value, run_id),
        )
        conn.commit()


def _set_reuse_mapping(
    db: EvaluationsDatabase,
    *,
    reuse_hash: str,
    user_id: str,
    run_id: str,
) -> None:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE idempotency_keys
            SET entity_id = ?
            WHERE user_id = ? AND entity_type = ? AND idempotency_key = ?
            """,
            (run_id, user_id, RECIPE_RUN_REUSE_ENTITY_TYPE, reuse_hash),
        )
        conn.commit()


def test_recipe_service_lists_and_fetches_builtin_manifests(tmp_path) -> None:
    _, service, _ = _service(tmp_path)

    manifests = service.list_manifests()

    assert {manifest.recipe_id for manifest in manifests} >= {
        "embeddings_model_selection",
        "summarization_quality",
    }

    manifest = service.get_manifest("summarization_quality")

    assert manifest.recipe_id == "summarization_quality"
    assert manifest.recipe_version == "1"


def test_recipe_service_rejects_non_launchable_stub_in_validate_dataset(tmp_path) -> None:
    _, service, _ = _service(tmp_path)

    with pytest.raises(
        RecipeDefinitionNotLaunchableError,
        match="rag_retrieval_tuning",
    ):
        service.validate_dataset(
            "rag_retrieval_tuning",
            dataset=[{"input": "find alpha", "expected": "alpha"}],
        )


def test_recipe_service_rejects_non_launchable_stub_in_create_run(tmp_path) -> None:
    _, service, _ = _service(tmp_path)

    with pytest.raises(
        RecipeDefinitionNotLaunchableError,
        match="rag_retrieval_tuning",
    ):
        service.create_run(
            "rag_retrieval_tuning",
            dataset=[{"input": "find alpha", "expected": "alpha"}],
            run_config={},
        )


def test_recipe_service_validates_dataset_shape_and_labeling_mode(tmp_path) -> None:
    _, service, _ = _service(tmp_path)

    result = service.validate_dataset(
        "summarization_quality",
        dataset=[
            {"input": "valid prompt", "expected": "summary"},
            {"input": "missing label partner"},
        ],
    )

    assert result["valid"] is False
    assert result["dataset_mode"] == "mixed"
    assert any("consistent labeling mode" in error for error in result["errors"])


def test_recipe_service_creates_parent_run_and_normalized_report_shell(tmp_path) -> None:
    _, service, _ = _service(tmp_path)
    dataset = _inline_dataset()
    run_config = _run_config()

    record = service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )

    assert record.status is RunStatus.PENDING
    assert record.dataset_content_hash == build_dataset_content_hash(dataset)
    assert record.metadata["run_config"] == run_config
    assert "reuse_hash" in record.metadata
    assert record.metadata["owner_user_id"]

    fetched = service.get_run(record.run_id)
    assert fetched is not None
    assert fetched.run_id == record.run_id
    assert fetched.metadata["run_config"] == run_config

    report = service.get_report(record.run_id)

    assert report.run.run_id == record.run_id
    assert set(report.recommendation_slots) == {
        "best_overall",
        "best_cheap",
        "best_local",
    }
    for slot in report.recommendation_slots.values():
        assert slot.candidate_run_id is None
        assert slot.reason_code is not None


def test_recipe_service_uses_embeddings_recipe_validation_and_normalization(tmp_path) -> None:
    _, service, _ = _service(tmp_path)
    dataset = [
        {
            "query_id": "q-1",
            "input": "find the alpha document",
            "expected_ids": ["1"],
        },
    ]
    run_config = {
        "comparison_mode": "embedding_only",
        "candidates": [
            {"model": "local:bge-small", "provider": "local", "is_local": True},
            {"model": "openai:text-embedding-3-small", "provider": "openai", "is_local": False},
        ],
    }

    validation = service.validate_dataset(
        "embeddings_model_selection",
        dataset=dataset,
    )

    assert validation["valid"] is True
    assert validation["dataset_mode"] == "labeled"
    assert validation["sample_count"] == 1

    reuse_hash_a = service.build_reuse_hash(
        "embeddings_model_selection",
        dataset=dataset,
        run_config=run_config,
    )
    reuse_hash_b = service.build_reuse_hash(
        "embeddings_model_selection",
        dataset=dataset,
        run_config={
            "comparison_mode": "embedding_only",
            "candidates": list(reversed(run_config["candidates"])),
        },
    )
    record = service.create_run(
        "embeddings_model_selection",
        dataset=dataset,
        run_config=run_config,
    )

    assert reuse_hash_a == reuse_hash_b
    assert record.metadata["run_config"]["comparison_mode"] == "embedding_only"
    assert [candidate["model"] for candidate in record.metadata["run_config"]["candidates"]] == [
        "local:bge-small",
        "openai:text-embedding-3-small",
    ]
    assert record.metadata["inline_dataset"] == dataset
    assert record.metadata["review_sample"] == {
        "required": False,
        "sample_size": 0,
        "sample_query_ids": [],
    }


def test_recipe_service_builds_embeddings_report_from_stored_recipe_inputs(tmp_path) -> None:
    db, service, _ = _service(tmp_path)
    dataset = [
        {"query_id": "q-1", "input": "alpha", "expected_ids": ["1"]},
        {"query_id": "q-2", "input": "beta", "expected_ids": ["2"]},
    ]
    record = service.create_run(
        "embeddings_model_selection",
        dataset=dataset,
        run_config={
            "comparison_mode": "embedding_only",
            "candidates": [
                {"model": "openai:text-embedding-3-small", "provider": "openai"},
                {"model": "local:bge-small", "provider": "local", "is_local": True},
            ],
        },
    )

    db.update_recipe_run(
        record.run_id,
        metadata={
            **record.metadata,
            "candidate_results": [
                {
                    "candidate_id": "arm-1",
                    "candidate_run_id": "child-run-1",
                    "model": "openai:text-embedding-3-small",
                    "provider": "openai",
                    "query_results": [
                        {
                            "ranked_ids": ["doc-1"],
                            "expected_ids": ["doc-1"],
                            "latency_ms": 100.0,
                        },
                        {
                            "ranked_ids": ["doc-2"],
                            "expected_ids": ["doc-2"],
                            "latency_ms": 105.0,
                        },
                    ],
                },
                {
                    "candidate_id": "arm-2",
                    "candidate_run_id": "child-run-2",
                    "model": "local:bge-small",
                    "provider": "local",
                    "is_local": True,
                    "query_results": [
                        {
                            "ranked_ids": ["doc-1"],
                            "expected_ids": ["doc-1"],
                            "latency_ms": 95.0,
                        },
                        {
                            "ranked_ids": ["doc-9"],
                            "expected_ids": ["doc-2"],
                            "latency_ms": 96.0,
                        },
                    ],
                },
            ],
        },
    )

    report = service.get_report(record.run_id)

    assert report.confidence_summary is not None
    assert report.recommendation_slots["best_overall"].candidate_run_id == "child-run-1"
    assert report.run.metadata["recipe_report"]["best_overall"]["candidate_id"] == "arm-1"


def test_recipe_service_builds_summarization_report_from_stored_recipe_inputs(tmp_path) -> None:
    db, service, _ = _service(tmp_path)
    record = service.create_run(
        "summarization_quality",
        dataset=_inline_dataset(),
        run_config=_run_config(),
    )

    db.update_recipe_run(
        record.run_id,
        metadata={
            **record.metadata,
            "recipe_report_inputs": {
                "dataset_mode": "labeled",
                "review_sample": {"required": False, "sample_size": 0, "sample_ids": []},
                "weights": {"grounding": 0.5, "coverage": 0.3, "usefulness": 0.2},
                "candidate_results": [
                    {
                        "candidate_id": "cand-openai",
                        "candidate_run_id": "cand-openai",
                        "provider": "openai",
                        "model": "gpt-4.1-mini",
                        "cost_usd": 0.01,
                        "sample_results": [
                            {
                                "sample_id": "math-1",
                                "metrics": {
                                    "grounding": 0.92,
                                    "coverage": 0.88,
                                    "usefulness": 0.80,
                                },
                                "latency_ms": 110.0,
                            },
                            {
                                "sample_id": "sky-1",
                                "metrics": {
                                    "grounding": 0.89,
                                    "coverage": 0.86,
                                    "usefulness": 0.81,
                                },
                                "latency_ms": 115.0,
                            },
                        ],
                    },
                    {
                        "candidate_id": "cand-local",
                        "candidate_run_id": "cand-local",
                        "provider": "ollama",
                        "model": "llama3.1:8b",
                        "is_local": True,
                        "cost_usd": 0.0,
                        "sample_results": [
                            {
                                "sample_id": "math-1",
                                "metrics": {
                                    "grounding": 0.80,
                                    "coverage": 0.77,
                                    "usefulness": 0.79,
                                },
                                "latency_ms": 80.0,
                            },
                            {
                                "sample_id": "sky-1",
                                "metrics": {
                                    "grounding": 0.78,
                                    "coverage": 0.76,
                                    "usefulness": 0.78,
                                },
                                "latency_ms": 82.0,
                            },
                        ],
                    },
                ],
            },
        },
    )

    report = service.get_report(record.run_id)

    assert report.confidence_summary is not None
    assert report.recommendation_slots["best_overall"].candidate_run_id == "cand-openai"
    assert report.recommendation_slots["best_local"].candidate_run_id == "cand-local"
    assert report.run.metadata["recipe_report"]["best_overall"]["candidate_id"] == "cand-openai"


def test_recipe_service_reuses_completed_run_unless_force_rerun(tmp_path) -> None:
    db, service, user_id = _service(tmp_path)
    dataset = _inline_dataset()
    run_config = _run_config()
    created = service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )
    reuse_hash = created.metadata["reuse_hash"]

    assert (
        db.lookup_idempotency(
            RECIPE_RUN_REUSE_ENTITY_TYPE,
            reuse_hash,
            user_id,
        )
        == created.run_id
    )

    _mark_recipe_run_completed(db, created.run_id)

    reused = service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )

    assert reused.run_id == created.run_id
    assert reused.status is RunStatus.COMPLETED
    assert (
        db.lookup_idempotency(
            RECIPE_RUN_REUSE_ENTITY_TYPE,
            reuse_hash,
            user_id,
        )
        == created.run_id
    )

    forced = service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
        force_rerun=True,
    )

    assert forced.run_id != created.run_id
    assert forced.status is RunStatus.PENDING


def test_recipe_service_repairs_stale_reuse_mapping_to_latest_completed_run(tmp_path) -> None:
    db, service, user_id = _service(tmp_path)
    dataset = _inline_dataset()
    run_config = _run_config()

    first_run = service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )
    reuse_hash = first_run.metadata["reuse_hash"]
    db.record_idempotency(
        RECIPE_RUN_REUSE_ENTITY_TYPE,
        reuse_hash,
        first_run.run_id,
        user_id,
    )

    forced_run = service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
        force_rerun=True,
    )
    _mark_recipe_run_completed(db, forced_run.run_id)
    _set_reuse_mapping(
        db,
        reuse_hash=reuse_hash,
        user_id=user_id,
        run_id=first_run.run_id,
    )

    reused = service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )

    assert reused.run_id == forced_run.run_id
    assert reused.status is RunStatus.COMPLETED
    assert (
        db.lookup_idempotency(
            RECIPE_RUN_REUSE_ENTITY_TYPE,
            reuse_hash,
            user_id,
        )
        == forced_run.run_id
    )


def test_recipe_service_does_not_reuse_completed_run_from_other_user(tmp_path) -> None:
    db, service, _ = _service(tmp_path)
    dataset = _inline_dataset()
    run_config = _run_config()

    other_user_service = RecipeRunsService(db=db, user_id="other-user")
    other_user_run = other_user_service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )
    _mark_recipe_run_completed(db, other_user_run.run_id)

    created = service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )

    assert created.run_id != other_user_run.run_id
    assert created.status is RunStatus.PENDING


def test_recipe_service_reuses_legacy_completed_run_without_owner_in_single_user_mode(tmp_path) -> None:
    db, service, _ = _service(tmp_path)
    dataset = _inline_dataset()
    run_config = _run_config()
    reuse_hash = service.build_reuse_hash(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )

    legacy_run_id = db.create_recipe_run(
        recipe_id="summarization_quality",
        recipe_version="1",
        status=RunStatus.COMPLETED,
        dataset_content_hash=build_dataset_content_hash(dataset),
        metadata={
            "run_config": run_config,
            "reuse_hash": reuse_hash,
        },
    )

    reused = service.create_run(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )

    assert reused.run_id == legacy_run_id
    assert reused.status is RunStatus.COMPLETED
