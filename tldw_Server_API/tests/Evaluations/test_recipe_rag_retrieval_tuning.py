from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Evaluations.recipes.rag_retrieval_tuning import (
    RAGRetrievalTuningRecipe,
)
from tldw_Server_API.app.core.Evaluations.recipes.rag_retrieval_tuning_candidates import (
    SUPPORTED_V1_KNOBS,
    build_auto_sweep,
)
from tldw_Server_API.app.core.Evaluations.recipes.rag_retrieval_tuning_execution import (
    build_unified_rag_request,
    plan_candidate_indexes,
    summarize_candidate_metrics,
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


def test_validate_dataset_rejects_empty_target_objects() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": {},
            }
        ],
        run_config={"corpus_scope": {"sources": ["media_db"], "media_ids": [10]}},
    )

    assert result["valid"] is False
    assert any("must include at least one supported target field" in error for error in result["errors"])


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


def test_validate_dataset_rejects_string_false_fixed_index_flags() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": {"relevant_chunk_ids": [{"id": "chunk-1", "grade": 2}]},
            }
        ],
        run_config={
            "corpus_scope": {
                "sources": ["media_db"],
                "media_ids": [10],
                "indexing_fixed": "false",
            },
            "chunking_fixed": "false",
        },
    )

    assert result["valid"] is False
    assert any("chunk-level targets require stable spans or fixed indexing" in error for error in result["errors"])


def test_validate_dataset_returns_structured_errors_for_invalid_fixed_index_flags() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[
            {
                "sample_id": "q-1",
                "query": "find the architecture note",
                "targets": {"relevant_chunk_ids": [{"id": "chunk-1", "grade": 2}]},
            }
        ],
        run_config={
            "corpus_scope": {"sources": ["media_db"], "media_ids": [10]},
            "chunking_fixed": "maybe",
        },
    )

    assert result["valid"] is False
    assert any("chunking_fixed" in error for error in result["errors"])


def test_validate_dataset_returns_structured_errors_for_bad_weak_supervision_budget() -> None:
    recipe = RAGRetrievalTuningRecipe()

    result = recipe.validate_dataset(
        dataset=[{"sample_id": "q-1", "query": "query 1"}],
        run_config={
            "corpus_scope": {"sources": ["media_db"], "media_ids": [10]},
            "weak_supervision_budget": {"max_review_samples": "bad"},
        },
    )

    assert result["valid"] is False
    assert any("weak_supervision_budget.max_review_samples" in error for error in result["errors"])


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


def test_index_affecting_candidates_receive_isolated_index_keys() -> None:
    plan = plan_candidate_indexes(
        corpus_scope={
            "sources": ["media_db", "notes"],
            "media_ids": ["1"],
            "note_ids": ["note-1"],
        },
        candidates=[
            {
                "candidate_id": "a",
                "indexing_config": {"chunking_preset": "baseline"},
                "retrieval_config": {"top_k": 10},
            },
            {
                "candidate_id": "b",
                "indexing_config": {"chunking_preset": "compact"},
                "retrieval_config": {"top_k": 10},
            },
            {
                "candidate_id": "c",
                "retrieval_config": {"top_k": 10},
            },
        ],
        dataset_content_hash="abc123",
        owner_user_id="user-1",
    )

    assert plan["a"].index_key != plan["b"].index_key
    assert plan["a"].mutates_live_index is False
    assert plan["c"].needs_rebuild is False


def test_identical_index_affecting_candidates_reuse_existing_index_plan() -> None:
    plan = plan_candidate_indexes(
        corpus_scope={"sources": ["media_db"], "media_ids": ["1"]},
        candidates=[
            {
                "candidate_id": "a",
                "indexing_config": {"chunking_preset": "compact"},
                "retrieval_config": {"top_k": 10},
            },
            {
                "candidate_id": "b",
                "indexing_config": {"chunking_preset": "compact"},
                "retrieval_config": {"top_k": 5},
            },
        ],
        dataset_content_hash="abc123",
        owner_user_id="user-1",
    )

    assert plan["a"].needs_rebuild is True
    assert plan["b"].needs_rebuild is False
    assert plan["b"].reuse_index_key == plan["a"].index_key


def test_candidate_index_plan_rejects_duplicate_candidate_ids() -> None:
    with pytest.raises(ValueError, match="candidate_id"):
        plan_candidate_indexes(
            corpus_scope={"sources": ["media_db"], "media_ids": ["1"]},
            candidates=[
                {
                    "candidate_id": "duplicate",
                    "indexing_config": {"chunking_preset": "compact"},
                    "retrieval_config": {"top_k": 10},
                },
                {
                    "candidate_id": "duplicate",
                    "retrieval_config": {"top_k": 5},
                },
            ],
            dataset_content_hash="abc123",
            owner_user_id="user-1",
        )


def test_execution_report_separates_first_pass_and_post_rerank_metrics() -> None:
    result = summarize_candidate_metrics(
        first_pass_hits=[{"grade": 3}, {"grade": 1}],
        reranked_hits=[{"grade": 3}, {"grade": 2}],
    )

    assert result["first_pass_recall_score"] <= result["post_rerank_quality_score"]
    assert "pre_rerank_recall_at_k" in result["metrics"]
    assert "post_rerank_ndcg_at_k" in result["metrics"]


def test_execution_report_uses_fixed_zero_to_three_grade_scale() -> None:
    result = summarize_candidate_metrics(
        first_pass_hits=[{"grade": 1}],
        reranked_hits=[{"grade": 1}],
    )

    assert result["metrics"]["pre_rerank_recall_at_k"] == pytest.approx(1 / 3, rel=1e-6)


def test_execution_report_clamps_out_of_range_grades_to_scale_ceiling() -> None:
    result = summarize_candidate_metrics(
        first_pass_hits=[{"grade": 99}],
        reranked_hits=[{"grade": 99}],
    )

    assert result["metrics"]["pre_rerank_recall_at_k"] == 1.0
    assert result["post_rerank_quality_score"] == 1.0


def test_build_unified_rag_request_maps_corpus_scope_and_candidate_settings() -> None:
    request = build_unified_rag_request(
        query="find the architecture note",
        corpus_scope={
            "sources": ["media_db", "notes"],
            "media_ids": ["10"],
            "note_ids": ["note-7"],
        },
        candidate={
            "retrieval_config": {
                "search_mode": "hybrid",
                "top_k": 8,
                "hybrid_alpha": 0.5,
                "enable_reranking": True,
                "reranking_strategy": "flashrank",
                "rerank_top_k": 5,
            }
        },
        index_key="rag-eval-index-1",
    )

    assert request.sources == ["media_db", "notes"]
    assert request.include_media_ids == [10]
    assert request.include_note_ids == ["note-7"]
    assert request.index_namespace == "rag-eval-index-1"
    assert request.rerank_top_k == 5
