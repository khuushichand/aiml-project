from __future__ import annotations

from typing import Any

from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import RunStatus
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_single_user_instance
from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.Evaluations.recipe_runs_service import (
    RECIPE_RUN_REUSE_ENTITY_TYPE,
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
