from __future__ import annotations

import pytest
import sqlite3

from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import RunStatus
from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.Evaluations.recipes.reporting import ConfidenceSummary, RecommendationSlot


def test_recipe_run_row_persists_snapshot_confidence_review_and_children(tmp_path) -> None:
    db = EvaluationsDatabase(str(tmp_path / "evaluations.db"))

    run_id = db.create_recipe_run(
        recipe_id="embeddings_model_selection",
        recipe_version="2026.03.29",
        status=RunStatus.RUNNING,
        dataset_snapshot_ref="snapshot://dataset-123@v4",
        dataset_content_hash="sha256:abc123",
        review_state="needs_review",
        confidence_summary=ConfidenceSummary(
            kind="bootstrap",
            confidence=0.74,
            sample_count=12,
            margin=0.12,
            judge_agreement=0.83,
        ),
        recommendation_slots={
            "best_overall": RecommendationSlot(
                candidate_run_id=None,
                reason_code="no_qualified_candidate",
                explanation="No candidate satisfied the hard gate.",
            ),
        },
        child_run_ids=["child-1", "child-2"],
    )

    record = db.get_recipe_run(run_id)

    assert record is not None
    assert record.status is RunStatus.RUNNING
    assert record.recipe_version == "2026.03.29"
    assert record.review_state == "needs_review"
    assert record.dataset_snapshot_ref == "snapshot://dataset-123@v4"
    assert record.dataset_content_hash == "sha256:abc123"
    assert record.confidence_summary is not None
    assert record.confidence_summary.kind == "bootstrap"
    assert record.confidence_summary.sample_count == 12
    assert record.recommendation_slots["best_overall"].candidate_run_id is None
    assert record.recommendation_slots["best_overall"].reason_code == "no_qualified_candidate"
    assert record.child_run_ids == ["child-1", "child-2"]


def test_recipe_run_children_default_to_empty_list(tmp_path) -> None:
    db = EvaluationsDatabase(str(tmp_path / "evaluations.db"))

    with pytest.raises(ValueError, match="dataset_snapshot_ref or dataset_content_hash"):
        db.create_recipe_run(
            recipe_id="summarization_quality",
            recipe_version="2026.03.29",
            status=RunStatus.PENDING,
        )

    parent_run_id = db.create_recipe_run(
        recipe_id="summarization_quality",
        recipe_version="2026.03.29",
        status=RunStatus.PENDING,
        dataset_snapshot_ref="snapshot://dataset-123@v1",
    )

    assert db.list_recipe_run_children(parent_run_id) == []

    db.set_recipe_run_children(parent_run_id, [])

    assert db.list_recipe_run_children(parent_run_id) == []


def test_set_recipe_run_children_rejects_missing_parent(tmp_path) -> None:
    db = EvaluationsDatabase(str(tmp_path / "evaluations.db"))

    with pytest.raises(ValueError, match="parent recipe run does not exist"):
        db.set_recipe_run_children("missing-parent", ["child-a"])


def test_create_recipe_run_rolls_back_when_child_links_fail(tmp_path) -> None:
    db = EvaluationsDatabase(str(tmp_path / "evaluations.db"))

    with pytest.raises(sqlite3.IntegrityError):
        db.create_recipe_run(
            run_id="recipe-run-atomic",
            recipe_id="embeddings_model_selection",
            recipe_version="2026.03.29",
            status=RunStatus.PENDING,
            dataset_content_hash="sha256:atomic",
            child_run_ids=["child-a", "child-a"],
        )

    assert db.get_recipe_run("recipe-run-atomic") is None


def test_create_recipe_run_rejects_raw_none_recommendation_slots(tmp_path) -> None:
    db = EvaluationsDatabase(str(tmp_path / "evaluations.db"))

    with pytest.raises(ValueError, match="RecommendationSlot"):
        db.create_recipe_run(
            run_id="recipe-run-none-slot",
            recipe_id="summarization_quality",
            recipe_version="2026.03.29",
            status=RunStatus.PENDING,
            dataset_snapshot_ref="snapshot://dataset-123@v1",
            recommendation_slots={"best_overall": None},
        )

    assert db.get_recipe_run("recipe-run-none-slot") is None
