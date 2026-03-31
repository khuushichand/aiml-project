from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Evaluations.recipes.rag_answer_quality import (
    RAGAnswerQualityRecipe,
)
from tldw_Server_API.app.core.Evaluations.recipes import rag_answer_quality_execution


def test_rag_answer_quality_validates_fixed_context_dataset_with_inline_contexts() -> None:
    recipe = RAGAnswerQualityRecipe()

    result = recipe.validate_dataset(
        [
            {
                "sample_id": "sample-1",
                "input": "What is the capital of France?",
                "expected_behavior": "answer",
                "inline_contexts": [
                    {
                        "source": "knowledge_base",
                        "text": "Paris is the capital and most populous city of France.",
                    }
                ],
            },
            {
                "sample_id": "sample-2",
                "input": "What should the assistant do here?",
                "expected_behavior": "answer",
                "inline_contexts": [{"source": "policy", "text": "Answer clearly."}],
            },
        ],
        run_config={"evaluation_mode": "fixed_context"},
    )

    assert result["valid"] is True
    assert result["dataset_mode"] == "labeled"
    assert result["errors"] == []


def test_rag_answer_quality_rejects_invalid_expected_behavior_and_mixed_labeling() -> None:
    recipe = RAGAnswerQualityRecipe()

    result = recipe.validate_dataset(
        [
            {
                "sample_id": "sample-1",
                "input": "What is the capital of France?",
                "expected_behavior": "answer",
                "inline_contexts": [{"source": "knowledge_base", "text": "Paris."}],
            },
            {
                "sample_id": "sample-2",
                "input": "What is the recommended action?",
                "expected_behavior": "maybe",
                "inline_contexts": [{"source": "policy", "text": "Hedge when uncertain."}],
            },
            {
                "sample_id": "sample-3",
                "input": "What should the assistant do next?",
            },
        ],
        run_config={"evaluation_mode": "fixed_context"},
    )

    assert result["valid"] is False
    assert result["dataset_mode"] == "mixed"
    assert any("expected_behavior" in error for error in result["errors"])
    assert any("consistent labeling mode" in error for error in result["errors"])


def test_rag_answer_quality_rejects_fixed_context_samples_without_resolved_contexts() -> None:
    recipe = RAGAnswerQualityRecipe()

    result = recipe.validate_dataset(
        [
            {
                "sample_id": "sample-1",
                "query": "What happened in the rollout?",
                "expected_behavior": "answer",
            }
        ],
        run_config={
            "evaluation_mode": "fixed_context",
            "context_snapshot_ref": "context-snapshot-1",
            "candidates": [{"provider": "openai", "model": "gpt-4.1-mini"}],
        },
    )

    assert result["valid"] is False
    assert any("actual context" in error for error in result["errors"])


@pytest.mark.parametrize("supervision_mode", ["reference_answer", "pairwise", "mixed"])
def test_rag_answer_quality_requires_reference_answers_for_supervised_modes(
    supervision_mode: str,
) -> None:
    recipe = RAGAnswerQualityRecipe()

    result = recipe.validate_dataset(
        [
            {
                "sample_id": "sample-1",
                "query": "What is the capital of France?",
                "expected_behavior": "answer",
                "inline_contexts": [{"source": "kb", "text": "Paris is the capital of France."}],
            }
        ],
        run_config={
            "evaluation_mode": "fixed_context",
            "supervision_mode": supervision_mode,
            "context_snapshot_ref": "context-snapshot-1",
            "candidates": [{"provider": "openai", "model": "gpt-4.1-mini"}],
        },
    )

    assert result["valid"] is False
    assert any("reference_answer" in error for error in result["errors"])


def test_rag_answer_quality_normalizes_run_config_and_requires_context_refs() -> None:
    recipe = RAGAnswerQualityRecipe()

    normalized = recipe.normalize_run_config(
        {
            "evaluation_mode": "fixed_context",
            "supervision_mode": "mixed",
            "context_snapshot_ref": "context-snapshot-1",
            "candidate_dimensions": [
                "prompt_variant",
                "generation_model",
                "prompt_variant",
            ],
            "weights": {
                "grounding": 3,
                "answer_relevance": 1,
                "format_style": 1,
                "abstention_behavior": 1,
            },
            "grounding_threshold": 0.72,
            "candidates": [
                {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "prompt_variant": "default",
                }
            ],
        }
    )

    assert normalized["evaluation_mode"] == "fixed_context"
    assert normalized["supervision_mode"] == "mixed"
    assert normalized["context_snapshot_ref"] == "context-snapshot-1"
    assert normalized["candidate_dimensions"] == [
        "generation_model",
        "prompt_variant",
    ]
    assert pytest.approx(sum(normalized["weights"].values()), rel=1e-9) == 1.0
    assert normalized["grounding_threshold"] == pytest.approx(0.72)

    normalized_without_anchor = recipe.normalize_run_config(
        {
            "evaluation_mode": "fixed_context",
            "supervision_mode": "rubric",
            "candidate_dimensions": ["generation_model"],
            "candidates": [{"provider": "openai", "model": "gpt-4.1-mini"}],
        }
    )
    assert normalized_without_anchor["candidate_dimensions"] == ["generation_model"]
    assert "context_snapshot_ref" not in normalized_without_anchor
    assert "run_anchor_ref" not in normalized_without_anchor
    assert "inline_contexts" not in normalized_without_anchor

    with pytest.raises(ValueError, match="retrieval_baseline_ref"):
        recipe.normalize_run_config(
            {
                "evaluation_mode": "live_end_to_end",
                "supervision_mode": "pairwise",
                "retrieval_baseline_ref": None,
                "candidate_dimensions": ["generation_model"],
                "candidates": [{"provider": "openai", "model": "gpt-4.1-mini"}],
            }
        )

    normalized_live = recipe.normalize_run_config(
        {
            "evaluation_mode": "live_end_to_end",
            "supervision_mode": "pairwise",
            "retrieval_baseline_ref": "baseline-run-42",
            "candidate_dimensions": ["generation_model"],
            "candidates": [{"provider": "openai", "model": "gpt-4.1-mini"}],
        }
    )
    assert normalized_live["retrieval_baseline_ref"] == "baseline-run-42"
    assert normalized_live["evaluation_mode"] == "live_end_to_end"

    with pytest.raises(ValueError, match="run_config.candidates"):
        recipe.normalize_run_config(
            {
                "evaluation_mode": "fixed_context",
                "supervision_mode": "rubric",
                "context_snapshot_ref": "context-snapshot-1",
                "candidates": [],
            }
        )


def test_rag_answer_quality_build_report_applies_grounding_gate_to_best_overall() -> None:
    recipe = RAGAnswerQualityRecipe()

    report = recipe.build_report(
        dataset_mode="labeled",
        review_sample={"required": False, "sample_size": 0, "sample_ids": []},
        grounding_threshold=0.7,
        weights={
            "grounding": 0.5,
            "answer_relevance": 0.25,
            "format_style": 0.15,
            "abstention_behavior": 0.1,
        },
        candidate_results=[
            {
                "candidate_id": "gated-high-score",
                "candidate_run_id": "gated-high-score",
                "provider": "local",
                "model": "llama3.1:8b",
                "is_local": True,
                "cost_usd": 0.0,
                "sample_results": [
                    {
                        "sample_id": "sample-1",
                        "metrics": {
                            "grounding": 0.52,
                            "answer_relevance": 0.97,
                            "format_style_compliance": 0.95,
                            "abstention_behavior": 0.90,
                        },
                        "latency_ms": 55.0,
                    }
                ],
            },
            {
                "candidate_id": "grounded-winner",
                "candidate_run_id": "grounded-winner",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "cost_usd": 0.08,
                "sample_results": [
                    {
                        "sample_id": "sample-1",
                        "metrics": {
                            "grounding": 0.82,
                            "answer_relevance": 0.84,
                            "format_style_compliance": 0.74,
                            "abstention_behavior": 0.76,
                        },
                        "latency_ms": 95.0,
                    }
                ],
            },
            {
                "candidate_id": "local-backup",
                "candidate_run_id": "local-backup",
                "provider": "ollama",
                "model": "qwen2.5:7b",
                "is_local": True,
                "cost_usd": 0.0,
                "sample_results": [
                    {
                        "sample_id": "sample-1",
                        "metrics": {
                            "grounding": 0.74,
                            "answer_relevance": 0.71,
                            "format_style_compliance": 0.70,
                            "abstention_behavior": 0.68,
                        },
                        "latency_ms": 62.0,
                    }
                ],
            },
        ],
    )

    assert report["best_overall"]["candidate_id"] == "grounded-winner"
    assert report["best_overall"]["metrics"]["grounding_gate_passed"] is True
    assert report["candidates"][0]["candidate_id"] == "grounded-winner"
    assert report["candidates"][1]["candidate_id"] == "local-backup"
    assert report["candidates"][2]["candidate_id"] == "gated-high-score"
    assert report["recommendation_slots"]["best_overall"]["candidate_run_id"] == "grounded-winner"
    assert report["recommendation_slots"]["best_quality"]["candidate_run_id"] == "grounded-winner"
    assert report["recommendation_slots"]["best_local"]["candidate_run_id"] == "gated-high-score"


def test_rag_answer_quality_rubric_mode_does_not_invoke_reference_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_run_geval(**kwargs):
        raise AssertionError(f"run_geval should not be called in rubric mode: {kwargs}")

    monkeypatch.setattr(rag_answer_quality_execution, "run_geval", _unexpected_run_geval)

    score_bundle = rag_answer_quality_execution._score_sample(
        query="What is the capital of France?",
        contexts=[{"source": "kb", "text": "Paris is the capital of France."}],
        answer="Paris is the capital of France.",
        reference_answer="Paris is the capital of France.",
        expected_behavior="answer",
        candidate={"formatting_citation_mode": "plain"},
        run_config={"judge_config": {"provider": "openai", "model": "gpt-4.1-mini"}},
        supervision_mode="rubric",
        grounding_threshold=0.7,
        weights={
            "grounding": 0.4,
            "answer_relevance": 0.3,
            "format_style": 0.2,
            "abstention_behavior": 0.1,
        },
    )

    assert score_bundle["reference_comparison"] is None
    assert score_bundle["pairwise"] is None


def test_rag_answer_quality_score_sample_derives_failure_labels() -> None:
    score_bundle = rag_answer_quality_execution._score_sample(
        query="What is the capital of France?",
        contexts=[{"source": "kb", "text": "Paris is the capital of France."}],
        answer="Berlin is the capital of Germany.",
        reference_answer=None,
        expected_behavior="answer",
        candidate={"formatting_citation_mode": "citations"},
        run_config={},
        supervision_mode="rubric",
        grounding_threshold=0.7,
        weights={
            "grounding": 0.4,
            "answer_relevance": 0.3,
            "format_style": 0.2,
            "abstention_behavior": 0.1,
        },
    )

    assert set(score_bundle["failure_labels"]) == {"hallucinated", "format_failure"}


def test_rag_answer_quality_build_report_surfaces_failure_examples() -> None:
    recipe = RAGAnswerQualityRecipe()

    report = recipe.build_report(
        dataset_mode="labeled",
        review_sample={"required": False, "sample_size": 0, "sample_ids": []},
        grounding_threshold=0.7,
        weights={
            "grounding": 0.4,
            "answer_relevance": 0.3,
            "format_style": 0.2,
            "abstention_behavior": 0.1,
        },
        candidate_results=[
            {
                "candidate_id": "candidate-a",
                "candidate_run_id": "candidate-a",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "cost_usd": 0.05,
                "sample_results": [
                    {
                        "sample_id": "sample-1",
                        "query": "What is the capital of France?",
                        "expected_behavior": "answer",
                        "answer": "Berlin is the capital of Germany.",
                        "failure_labels": ["hallucinated", "format_failure"],
                        "metrics": {
                            "grounding": 0.25,
                            "answer_relevance": 0.55,
                            "format_style": 0.45,
                            "abstention_behavior": 0.9,
                        },
                        "latency_ms": 91.0,
                    }
                ],
            }
        ],
    )

    assert report["candidates"][0]["failure_label_counts"] == {
        "format_failure": 1,
        "hallucinated": 1,
    }
    assert report["failure_examples"][0]["candidate_id"] == "candidate-a"
    assert report["failure_examples"][0]["sample_id"] == "sample-1"
    assert report["failure_examples"][0]["failure_labels"] == [
        "hallucinated",
        "format_failure",
    ]
