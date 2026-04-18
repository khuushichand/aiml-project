from __future__ import annotations

from tldw_Server_API.app.api.v1.schemas.evaluation_recipe_schemas import RecipeManifest
from tldw_Server_API.app.core.Evaluations.recipes.rag_answer_quality import (
    RAGAnswerQualityRecipe,
)
from tldw_Server_API.app.core.Evaluations.recipes.registry import (
    RecipeNotFoundError,
    get_builtin_recipe_registry,
)


def test_builtin_recipe_manifests_are_indexed_by_id() -> None:
    registry = get_builtin_recipe_registry()

    manifests = registry.list_manifests()

    assert set(manifests) >= {
        "embeddings_model_selection",
        "summarization_quality",
        "rag_answer_quality",
    }
    assert manifests["embeddings_model_selection"].recipe_id == "embeddings_model_selection"
    assert manifests["summarization_quality"].recipe_id == "summarization_quality"
    assert manifests["rag_answer_quality"].recipe_id == "rag_answer_quality"
    assert manifests["rag_answer_quality"].launchable is True


def test_registry_exposes_rag_answer_quality_manifest() -> None:
    registry = get_builtin_recipe_registry()
    manifest = registry.get_manifest("rag_answer_quality")
    recipe = registry.get_recipe("rag_answer_quality")

    assert manifest.recipe_id == "rag_answer_quality"
    assert manifest.launchable is True
    assert isinstance(recipe, RAGAnswerQualityRecipe)
    assert manifest.supported_modes == ["labeled", "unlabeled"]
    assert manifest.capabilities["evaluation_modes"] == [
        "fixed_context",
        "live_end_to_end",
    ]
    assert manifest.capabilities["supervision_modes"] == [
        "rubric",
        "reference_answer",
        "pairwise",
        "mixed",
    ]
    assert manifest.capabilities["candidate_dimensions"] == [
        "generation_model",
        "prompt_variant",
        "formatting_citation_mode",
    ]
    assert manifest.default_run_config["evaluation_mode"] == "fixed_context"
    assert manifest.default_run_config["supervision_mode"] == "rubric"
    assert manifest.default_run_config["candidate_dimensions"] == [
        "generation_model",
        "prompt_variant",
        "formatting_citation_mode",
    ]


def test_recipe_manifest_supports_richer_metadata() -> None:
    manifest = RecipeManifest(
        recipe_id="rag_answer_quality",
        recipe_version="1",
        name="RAG Answer Quality",
        description="Compare answer-generation candidates with fixed-context and live supervision.",
        supported_modes=["labeled", "unlabeled"],
        tags=["rag", "answer-quality"],
        capabilities={
            "evaluation_modes": ["fixed_context", "live_end_to_end"],
            "supervision_modes": ["rubric", "reference_answer", "pairwise", "mixed"],
            "candidate_dimensions": [
                "generation_model",
                "prompt_variant",
                "formatting_citation_mode",
            ],
        },
        default_run_config={
            "evaluation_mode": "fixed_context",
            "supervision_mode": "rubric",
            "candidate_dimensions": [
                "generation_model",
                "prompt_variant",
                "formatting_citation_mode",
            ],
        },
    )

    assert manifest.capabilities["evaluation_modes"] == ["fixed_context", "live_end_to_end"]
    assert manifest.default_run_config["evaluation_mode"] == "fixed_context"


def test_registry_raises_specific_error_for_unknown_recipe() -> None:
    registry = get_builtin_recipe_registry()

    try:
        registry.get_recipe("missing-recipe")
    except RecipeNotFoundError as exc:
        assert exc.recipe_id == "missing-recipe"
        assert "missing-recipe" in str(exc)
    else:
        raise AssertionError("expected RecipeNotFoundError")
