from __future__ import annotations

from tldw_Server_API.app.api.v1.schemas.evaluation_recipe_schemas import RecipeManifest
from tldw_Server_API.app.core.Evaluations.recipes.registry import get_builtin_recipe_registry


def test_builtin_recipe_manifests_are_indexed_by_id() -> None:
    registry = get_builtin_recipe_registry()

    manifests = registry.list_manifests()

    assert set(manifests) >= {
        "embeddings_model_selection",
        "summarization_quality",
    }
    assert manifests["embeddings_model_selection"].recipe_id == "embeddings_model_selection"
    assert manifests["summarization_quality"].recipe_id == "summarization_quality"


def test_registry_exposes_rag_retrieval_tuning_manifest() -> None:
    registry = get_builtin_recipe_registry()
    manifest = registry.get_manifest("rag_retrieval_tuning")

    assert manifest.recipe_id == "rag_retrieval_tuning"
    assert manifest.supported_modes == ["labeled", "unlabeled"]
    assert manifest.capabilities["corpus_sources"] == ["media_db", "notes"]
    assert manifest.capabilities["candidate_creation_modes"] == ["auto_sweep", "manual"]


def test_recipe_manifest_supports_richer_metadata() -> None:
    manifest = RecipeManifest(
        recipe_id="rag_retrieval_tuning",
        recipe_version="1",
        name="RAG Retrieval Tuning",
        description="Tune retrieval candidates against labeled and unlabeled corpora.",
        supported_modes=["labeled", "unlabeled"],
        tags=["rag", "retrieval", "tuning"],
        capabilities={
            "corpus_sources": ["media_db", "notes"],
            "candidate_creation_modes": ["auto_sweep", "manual"],
        },
        default_run_config={
            "corpus_sources": ["media_db", "notes"],
            "candidate_creation_mode": "auto_sweep",
        },
    )

    assert manifest.capabilities["candidate_creation_modes"] == ["auto_sweep", "manual"]
    assert manifest.default_run_config["candidate_creation_mode"] == "auto_sweep"
