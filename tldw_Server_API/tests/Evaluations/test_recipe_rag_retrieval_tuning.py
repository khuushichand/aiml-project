from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Evaluations.recipes.rag_retrieval_tuning import (
    RAGRetrievalTuningRecipe,
)
from tldw_Server_API.app.core.Evaluations.recipes.rag_retrieval_tuning_candidates import (
    SUPPORTED_V1_KNOBS,
    build_auto_sweep,
)


def test_validate_dataset_accepts_run_level_media_and_note_scope_with_graded_targets() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": {
                    "relevant_media_ids": [{"id": 10, "grade": 3}],
                    "relevant_note_ids": [{"id": "note-7", "grade": 2}],
                    "relevant_spans": [
                        {
                            "source": "media_db",
                            "record_id": "10",
                            "start": 200,
                            "end": 260,
                            "grade": 3,
                        }
                    ],
                },
            }
        ],
        run_config={
            "corpus_scope": {
                "sources": ["media_db", "notes"],
                "media_ids": [10],
                "note_ids": ["note-7"],
            }
        },
    )

    assert result["valid"] is True
    assert result["dataset_mode"] == "labeled"
    assert result["errors"] == []


def test_validate_dataset_reserves_review_sample_for_weak_supervision() -> None:
    recipe = RAGRetrievalTuningRecipe()
    dataset = [
        {"sample_id": f"q-{index}", "query": f"query {index}"}
        for index in range(12)
    ]

    result = recipe.validate_dataset(
        dataset=dataset,
        run_config={"corpus_scope": {"sources": ["media_db"], "media_ids": [10]}},
    )

    assert result["valid"] is True
    assert result["dataset_mode"] == "unlabeled"
    assert result["review_sample"]["required"] is True
    assert result["review_sample"]["sample_size"] == 3
    assert result["review_sample"]["sample_ids"] == ["q-0", "q-1", "q-2"]


def test_validate_dataset_rejects_mixed_labeled_and_unlabeled_samples() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": {"relevant_media_ids": [{"id": 10, "grade": 3}]},
            },
            {"sample_id": "q-2", "query": "find the project update"},
        ],
        run_config={"corpus_scope": {"sources": ["media_db"], "media_ids": [10]}},
    )

    assert result["valid"] is False
    assert result["dataset_mode"] == "mixed"
    assert any("consistent labeling mode" in error for error in result["errors"])


def test_validate_dataset_requires_run_level_corpus_scope() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": {"relevant_note_ids": [{"id": "note-7", "grade": 2}]},
            }
        ],
        run_config=None,
    )

    assert result["valid"] is False
    assert any("run_config.corpus_scope" in error for error in result["errors"])


def test_validate_dataset_rejects_targets_outside_declared_corpus_scope() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": {
                    "relevant_media_ids": [{"id": 99, "grade": 3}],
                    "relevant_note_ids": [{"id": "note-9", "grade": 2}],
                    "relevant_spans": [
                        {
                            "source": "media_db",
                            "record_id": "99",
                            "start": 200,
                            "end": 260,
                            "grade": 3,
                        },
                        {
                            "source": "notes",
                            "record_id": "note-9",
                            "start": 0,
                            "end": 50,
                            "grade": 2,
                        },
                    ],
                },
            }
        ],
        run_config={
            "corpus_scope": {
                "sources": ["media_db", "notes"],
                "media_ids": [10],
                "note_ids": ["note-7"],
            }
        },
    )

    assert result["valid"] is False
    assert any("outside the declared corpus_scope.media_ids" in error for error in result["errors"])
    assert any("outside the declared corpus_scope.note_ids" in error for error in result["errors"])


def test_validate_dataset_rejects_empty_target_collections() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": {"relevant_media_ids": []},
            }
        ],
        run_config={"corpus_scope": {"sources": ["media_db"], "media_ids": [10]}},
    )

    assert result["valid"] is False
    assert result["dataset_mode"] == "labeled"
    assert any("non-empty relevant_media_ids list" in error for error in result["errors"])


def test_validate_dataset_returns_structured_errors_for_malformed_samples() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=["not-a-mapping"],
        run_config={"corpus_scope": {"sources": ["media_db"], "media_ids": [10]}},
    )

    assert result["valid"] is False
    assert any("must be an object" in error for error in result["errors"])


def test_validate_dataset_rejects_falsy_non_object_targets() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": [],
            }
        ],
        run_config={"corpus_scope": {"sources": ["media_db"], "media_ids": [10]}},
    )

    assert result["valid"] is False
    assert any("targets must be an object" in error for error in result["errors"])


def test_validate_dataset_returns_structured_errors_for_bad_numeric_fields() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": {
                    "relevant_media_ids": [{"id": 10, "grade": "bad"}],
                    "relevant_spans": [
                        {
                            "source": "media_db",
                            "record_id": "10",
                            "start": "a",
                            "end": 260,
                            "grade": 2,
                        }
                    ],
                },
            }
        ],
        run_config={"corpus_scope": {"sources": ["media_db"], "media_ids": [10]}},
    )

    assert result["valid"] is False
    assert any("integer grade" in error for error in result["errors"])
    assert any("integer start and end offsets" in error for error in result["errors"])


def test_normalize_run_config_supports_manual_candidates_and_defaults() -> None:
    recipe = RAGRetrievalTuningRecipe()

    normalized = recipe.normalize_run_config(
        {
            "candidate_creation_mode": "manual",
            "corpus_scope": {
                "sources": ["media_db", "notes"],
                "media_ids": [10],
                "note_ids": ["note-7"],
            },
            "candidates": [
                {
                    "candidate_id": "manual-a",
                    "retrieval_config": {
                        "search_mode": "hybrid",
                        "top_k": 8,
                        "hybrid_alpha": 0.5,
                        "enable_reranking": True,
                        "reranking_strategy": "flashrank",
                        "rerank_top_k": 8,
                    },
                }
            ],
        }
    )

    assert normalized["candidate_creation_mode"] == "manual"
    assert normalized["weak_supervision_budget"]["review_sample_fraction"] == 0.2
    assert normalized["weak_supervision_budget"]["max_review_samples"] == 25
    assert normalized["candidates"][0]["candidate_id"] == "manual-a"
    assert normalized["candidates"][0]["retrieval_config"]["top_k"] == 8


def test_auto_sweep_rejects_non_whitelisted_knobs() -> None:
    recipe = RAGRetrievalTuningRecipe()

    with pytest.raises(ValueError, match="unsupported candidate knob"):
        recipe.normalize_run_config(
            {
                "candidate_creation_mode": "manual",
                "candidates": [{"retrieval_config": {"llm_query_rewrite": True}}],
                "corpus_scope": {"sources": ["media_db"], "media_ids": [1]},
            }
        )


def test_auto_sweep_builds_bounded_candidates_with_supported_knobs_only() -> None:
    candidates = build_auto_sweep(
        {
            "search_mode": "hybrid",
            "top_k": 10,
            "hybrid_alpha": 0.7,
            "enable_reranking": True,
            "reranking_strategy": "flashrank",
            "rerank_top_k": 10,
        }
    )

    assert 1 < len(candidates) <= 8
    for candidate in candidates:
        assert set(candidate["retrieval_config"]).issubset(SUPPORTED_V1_KNOBS)


def test_normalize_run_config_parses_string_false_for_enable_reranking() -> None:
    recipe = RAGRetrievalTuningRecipe()

    normalized = recipe.normalize_run_config(
        {
            "candidate_creation_mode": "manual",
            "corpus_scope": {"sources": ["media_db"], "media_ids": [10]},
            "candidates": [
                {
                    "candidate_id": "manual-rerank-off",
                    "retrieval_config": {
                        "enable_reranking": "false",
                        "reranking_strategy": "none",
                    },
                }
            ],
        }
    )

    assert normalized["candidates"][0]["retrieval_config"]["enable_reranking"] is False
