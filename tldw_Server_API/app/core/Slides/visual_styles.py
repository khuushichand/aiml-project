"""Built-in visual style presets for slide generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.Slides.visual_style_catalog import (
    get_builtin_visual_style_definition,
    list_builtin_visual_style_definitions,
)


@dataclass(frozen=True)
class VisualStylePreset:
    """Resolved built-in visual style definition for compatibility callers."""

    style_id: str
    name: str
    description: str
    version: int
    generation_rules: dict[str, Any]
    artifact_preferences: tuple[str, ...]
    appearance_defaults: dict[str, Any]
    fallback_policy: dict[str, Any]


def _project_definition(definition) -> VisualStylePreset:
    return VisualStylePreset(
        style_id=definition.style_id,
        name=definition.name,
        description=definition.description,
        version=definition.version,
        generation_rules=dict(definition.generation_rules),
        artifact_preferences=tuple(definition.artifact_preferences),
        appearance_defaults={"theme": definition.base_theme},
        fallback_policy=dict(definition.fallback_policy),
    )


def list_builtin_visual_styles() -> list[VisualStylePreset]:
    """Return all built-in visual style presets."""

    return [_project_definition(definition) for definition in list_builtin_visual_style_definitions()]


def get_builtin_visual_style(style_id: str) -> VisualStylePreset | None:
    """Look up a built-in visual style by identifier."""

    definition = get_builtin_visual_style_definition(style_id)
    if definition is None:
        return None
    return _project_definition(definition)
