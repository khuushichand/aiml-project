from __future__ import annotations

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
