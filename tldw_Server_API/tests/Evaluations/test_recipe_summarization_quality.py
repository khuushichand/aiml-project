from __future__ import annotations

from tldw_Server_API.app.core.Evaluations.recipes.summarization_quality import (
    SummarizationQualityRecipe,
)


def test_summarization_recipe_validates_unlabeled_dataset_and_reserves_review_sample() -> None:
    recipe = SummarizationQualityRecipe()

    result = recipe.validate_dataset(
        [
            {"input": "First source text."},
            {"input": "Second source text."},
            {"input": "Third source text."},
            {"input": "Fourth source text."},
        ]
    )

    assert result["valid"] is True
    assert result["dataset_mode"] == "unlabeled"
    assert result["review_sample"]["required"] is True
    assert result["review_sample"]["sample_size"] == 3
    assert result["review_sample"]["sample_ids"] == ["sample-0", "sample-1", "sample-2"]


def test_summarization_recipe_builds_weighted_report_from_geval_metrics() -> None:
    recipe = SummarizationQualityRecipe()

    report = recipe.build_report(
        dataset_mode="labeled",
        review_sample={"required": False, "sample_size": 0, "sample_ids": []},
        weights={"grounding": 0.5, "coverage": 0.3, "usefulness": 0.2},
        candidate_results=[
            {
                "candidate_id": "candidate-openai",
                "candidate_run_id": "candidate-openai",
                "model": "gpt-4.1-mini",
                "provider": "openai",
                "cost_usd": 0.02,
                "sample_results": [
                    {
                        "sample_id": "sample-0",
                        "metrics": {
                            "grounding": 0.90,
                            "coverage": 0.85,
                            "usefulness": 0.80,
                        },
                        "latency_ms": 120.0,
                    },
                    {
                        "sample_id": "sample-1",
                        "metrics": {
                            "grounding": 0.86,
                            "coverage": 0.84,
                            "usefulness": 0.79,
                        },
                        "latency_ms": 140.0,
                    },
                ],
            },
            {
                "candidate_id": "candidate-local",
                "candidate_run_id": "candidate-local",
                "model": "llama3.1:8b",
                "provider": "ollama",
                "is_local": True,
                "cost_usd": 0.0,
                "sample_results": [
                    {
                        "sample_id": "sample-0",
                        "metrics": {
                            "grounding": 0.82,
                            "coverage": 0.80,
                            "usefulness": 0.81,
                        },
                        "latency_ms": 80.0,
                    },
                    {
                        "sample_id": "sample-1",
                        "metrics": {
                            "grounding": 0.81,
                            "coverage": 0.78,
                            "usefulness": 0.80,
                        },
                        "latency_ms": 82.0,
                    },
                ],
            },
        ],
    )

    assert report["best_overall"]["candidate_id"] == "candidate-openai"
    assert report["best_cheap"]["candidate_id"] == "candidate-local"
    assert report["best_local"]["candidate_id"] == "candidate-local"
    assert report["recommendation_slots"]["best_overall"]["candidate_run_id"] == "candidate-openai"
    assert report["candidates"][0]["metrics"]["quality_score"] > report["candidates"][1]["metrics"]["quality_score"]
    assert report["confidence_summary"]["sample_count"] == 2
    assert report["confidence_inputs"]["winner_margin"] > 0.0
