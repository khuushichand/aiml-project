"""Built-in recipe registry."""

from __future__ import annotations

from collections.abc import Iterable

from tldw_Server_API.app.api.v1.schemas.evaluation_recipe_schemas import RecipeManifest

from .base import RecipeDefinition
from .embeddings_retrieval import EmbeddingsRetrievalRecipe
from .rag_answer_quality import RAGAnswerQualityRecipe
from .rag_retrieval_tuning import RAGRetrievalTuningRecipe
from .summarization_quality import SummarizationQualityRecipe


def _default_builtin_recipes() -> tuple[RecipeDefinition, ...]:
    return (
        EmbeddingsRetrievalRecipe(),
        SummarizationQualityRecipe(),
        RAGRetrievalTuningRecipe(),
        RAGAnswerQualityRecipe(),
    )


class RecipeRegistry:
    """Registry of recipe definitions indexed by recipe id."""

    def __init__(self, recipes: Iterable[RecipeDefinition] | None = None) -> None:
        recipe_iterable = tuple(recipes) if recipes is not None else _default_builtin_recipes()
        self._recipes: dict[str, RecipeDefinition] = {}
        for recipe in recipe_iterable:
            self._recipes[recipe.recipe_id] = recipe

    def list_manifests(self) -> dict[str, RecipeManifest]:
        return {recipe_id: recipe.get_manifest() for recipe_id, recipe in self._recipes.items()}

    def get_manifest(self, recipe_id: str) -> RecipeManifest:
        return self._recipes[recipe_id].get_manifest()

    def get_recipe(self, recipe_id: str) -> RecipeDefinition:
        return self._recipes[recipe_id]

    def recipe_ids(self) -> list[str]:
        return list(self._recipes)


def get_builtin_recipe_registry() -> RecipeRegistry:
    return RecipeRegistry()
