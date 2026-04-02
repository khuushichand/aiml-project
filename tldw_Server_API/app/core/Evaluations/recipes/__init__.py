"""Recipe framework primitives for evaluations."""

from .base import RecipeDefinition, StaticRecipeDefinition
from .dataset_snapshot import DatasetSnapshot, build_dataset_content_hash, build_dataset_snapshot_ref
from .registry import RecipeRegistry, get_builtin_recipe_registry
from .reporting import ConfidenceSummary, RecommendationSlot, RecipeRunReport

__all__ = [
    "ConfidenceSummary",
    "DatasetSnapshot",
    "RecipeDefinition",
    "RecipeRegistry",
    "RecipeRunReport",
    "RecommendationSlot",
    "StaticRecipeDefinition",
    "build_dataset_content_hash",
    "build_dataset_snapshot_ref",
    "get_builtin_recipe_registry",
]
