"""Resolve built-in visual style catalog entries into snapshots and appearance."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.Slides.visual_style_catalog import (
    BuiltinVisualStyleDefinition,
    get_builtin_visual_style_definition,
)
from tldw_Server_API.app.core.Slides.visual_style_packs import (
    get_visual_style_pack,
    render_pack_custom_css,
    resolve_pack_settings,
    resolve_pack_token_overrides,
)


@dataclass(frozen=True)
class ResolvedBuiltinVisualStyle:
    """Resolved built-in style payload."""

    definition: BuiltinVisualStyleDefinition
    snapshot: dict[str, Any]
    appearance: dict[str, Any]


def _build_snapshot(
    definition: BuiltinVisualStyleDefinition,
    *,
    token_overrides: dict[str, Any],
    resolved_settings: dict[str, Any],
    resolved_theme: str,
    resolved_marp_theme: str | None,
) -> dict[str, Any]:
    """Build the compact persisted snapshot for a resolved built-in style."""

    return {
        "id": definition.style_id,
        "scope": "builtin",
        "name": definition.name,
        "version": definition.version,
        "description": definition.description,
        "category": definition.category,
        "guide_number": definition.guide_number,
        "sort_order": definition.sort_order,
        "prompt_profile": definition.prompt_profile,
        "style_pack": definition.style_pack,
        "style_pack_version": definition.style_pack_version,
        "base_theme": definition.base_theme,
        "generation_rules": deepcopy(definition.generation_rules),
        "artifact_preferences": list(definition.artifact_preferences),
        "fallback_policy": deepcopy(definition.fallback_policy),
        "tags": list(definition.tags),
        "best_for": list(definition.best_for),
        "resolution": {
            "base_theme": definition.base_theme,
            "resolved_theme": resolved_theme,
            "resolved_marp_theme": resolved_marp_theme,
            "style_pack": definition.style_pack,
            "style_pack_version": definition.style_pack_version,
            "token_overrides": deepcopy(token_overrides),
            "resolved_settings": deepcopy(resolved_settings),
        },
    }

def resolve_builtin_visual_style(
    style_id: str,
    *,
    include_custom_css: bool = True,
) -> ResolvedBuiltinVisualStyle | None:
    """Resolve a built-in style id into compact snapshot metadata and appearance."""

    definition = get_builtin_visual_style_definition(style_id)
    if definition is None:
        return None

    pack = get_visual_style_pack(definition.style_pack)
    appearance_overrides = (
        dict(definition.appearance_overrides)
        if isinstance(definition.appearance_overrides, dict)
        else {}
    )
    style_token_overrides = appearance_overrides.get("token_overrides")
    token_overrides = resolve_pack_token_overrides(
        definition.style_pack,
        token_overrides=style_token_overrides if isinstance(style_token_overrides, dict) else None,
    )
    settings_overrides = appearance_overrides.get("settings")
    resolved_settings = resolve_pack_settings(
        definition.style_pack,
        settings_overrides=settings_overrides if isinstance(settings_overrides, dict) else None,
    )

    resolved_theme = str(appearance_overrides.get("theme") or definition.base_theme)
    resolved_marp_theme_value = appearance_overrides.get("marp_theme")
    resolved_marp_theme = str(resolved_marp_theme_value) if isinstance(resolved_marp_theme_value, str) else None
    custom_css = None
    if include_custom_css:
        custom_css = render_pack_custom_css(
            style_id=definition.style_id,
            pack_id=pack.pack_id if pack is not None else definition.style_pack,
            token_overrides=token_overrides,
        )

    snapshot = _build_snapshot(
        definition,
        token_overrides=token_overrides,
        resolved_settings=resolved_settings,
        resolved_theme=resolved_theme,
        resolved_marp_theme=resolved_marp_theme,
    )
    appearance = {
        "theme": resolved_theme,
        "marp_theme": resolved_marp_theme,
        "settings": deepcopy(resolved_settings),
        "custom_css": custom_css,
    }
    return ResolvedBuiltinVisualStyle(
        definition=definition,
        snapshot=snapshot,
        appearance=appearance,
    )
