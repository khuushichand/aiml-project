"""Reusable resolved appearance packs for built-in slide visual styles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VisualStylePack:
    """Reusable deck-appearance pack."""

    pack_id: str
    version: int
    default_token_overrides: dict[str, Any]
    default_resolved_settings: dict[str, Any]


_VISUAL_STYLE_PACKS: tuple[VisualStylePack, ...] = (
    VisualStylePack(
        pack_id="hand_drawn_surface",
        version=1,
        default_token_overrides={
            "surface": "#101418",
            "text": "#f8f2c8",
            "accent": "#fef08a",
            "border": "#f8f2c8",
        },
        default_resolved_settings={"controls": True, "progress": False},
    ),
    VisualStylePack(
        pack_id="technical_grid",
        version=1,
        default_token_overrides={
            "surface": "#0f172a",
            "text": "#f8fafc",
            "accent": "#7dd3fc",
            "grid": "rgba(125, 211, 252, 0.16)",
        },
        default_resolved_settings={"controls": True, "progress": True},
    ),
    VisualStylePack(
        pack_id="isometric_clean",
        version=1,
        default_token_overrides={
            "surface": "#ffffff",
            "text": "#0f172a",
            "accent": "#2563eb",
        },
        default_resolved_settings={"controls": True, "progress": True},
    ),
    VisualStylePack(
        pack_id="isometric_dark",
        version=1,
        default_token_overrides={
            "surface": "#111827",
            "text": "#e5e7eb",
            "accent": "#7dd3fc",
        },
        default_resolved_settings={"controls": True, "progress": True, "backgroundTransition": "fade"},
    ),
    VisualStylePack(
        pack_id="dashboard_glass",
        version=1,
        default_token_overrides={
            "surface": "rgba(15, 23, 42, 0.72)",
            "text": "#f8fafc",
            "accent": "#38bdf8",
            "glow": "#67e8f9",
        },
        default_resolved_settings={"controls": True, "progress": True, "transition": "slide"},
    ),
    VisualStylePack(
        pack_id="editorial_print",
        version=1,
        default_token_overrides={
            "surface": "#ffffff",
            "text": "#111111",
            "accent": "#111111",
            "rule": "#d4d4d8",
        },
        default_resolved_settings={"controls": False, "progress": False},
    ),
    VisualStylePack(
        pack_id="tactile_soft",
        version=1,
        default_token_overrides={
            "surface": "#faf5ff",
            "text": "#1f2937",
            "accent": "#c084fc",
            "shadow": "rgba(15, 23, 42, 0.12)",
        },
        default_resolved_settings={"controls": True, "progress": True},
    ),
    VisualStylePack(
        pack_id="retro_pixel",
        version=1,
        default_token_overrides={
            "surface": "#111827",
            "text": "#f9fafb",
            "accent": "#22c55e",
            "pixel": "4px",
        },
        default_resolved_settings={"controls": True, "progress": True, "transition": "convex"},
    ),
    VisualStylePack(
        pack_id="neon_cinematic",
        version=1,
        default_token_overrides={
            "surface": "#020617",
            "text": "#f8fafc",
            "accent": "#f97316",
            "glow": "#67e8f9",
        },
        default_resolved_settings={"controls": True, "progress": True},
    ),
    VisualStylePack(
        pack_id="brutalist_editorial",
        version=1,
        default_token_overrides={
            "surface": "#f5f5f5",
            "text": "#000000",
            "accent": "#000000",
            "border": "#000000",
        },
        default_resolved_settings={"controls": True, "progress": False, "transition": "none"},
    ),
    VisualStylePack(
        pack_id="heritage_formal",
        version=1,
        default_token_overrides={
            "surface": "#fffbf5",
            "text": "#3f2a14",
            "accent": "#6b4f2a",
            "rule": "#b45309",
        },
        default_resolved_settings={"controls": False, "progress": False},
    ),
    VisualStylePack(
        pack_id="pastel_character",
        version=1,
        default_token_overrides={
            "surface": "#fff1f2",
            "text": "#1f2937",
            "accent": "#fb7185",
            "shadow": "rgba(244, 114, 182, 0.2)",
        },
        default_resolved_settings={"controls": True, "progress": True},
    ),
)

_VISUAL_STYLE_PACKS_BY_ID = {pack.pack_id: pack for pack in _VISUAL_STYLE_PACKS}


def _clone_pack(pack: VisualStylePack) -> VisualStylePack:
    """Return a defensive copy of a style pack."""

    return VisualStylePack(
        pack_id=pack.pack_id,
        version=pack.version,
        default_token_overrides=dict(pack.default_token_overrides),
        default_resolved_settings=dict(pack.default_resolved_settings),
    )


def list_visual_style_packs() -> list[VisualStylePack]:
    """Return all reusable style packs."""

    return [_clone_pack(pack) for pack in _VISUAL_STYLE_PACKS]


def get_visual_style_pack(pack_id: str) -> VisualStylePack | None:
    """Look up a style pack by identifier."""

    pack = _VISUAL_STYLE_PACKS_BY_ID.get(pack_id)
    return _clone_pack(pack) if pack is not None else None


def resolve_pack_token_overrides(
    pack_id: str,
    *,
    token_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge pack defaults with optional style-specific token overrides."""

    pack = _VISUAL_STYLE_PACKS_BY_ID.get(pack_id)
    if pack is None:
        return dict(token_overrides or {})
    resolved = dict(pack.default_token_overrides)
    if token_overrides:
        resolved.update(token_overrides)
    return resolved


def resolve_pack_settings(
    pack_id: str,
    *,
    settings_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge pack defaults with optional style-specific settings overrides."""

    pack = _VISUAL_STYLE_PACKS_BY_ID.get(pack_id)
    if pack is None:
        return dict(settings_overrides or {})
    resolved = dict(pack.default_resolved_settings)
    if settings_overrides:
        resolved.update(settings_overrides)
    return resolved


def render_pack_custom_css(
    *,
    style_id: str,
    pack_id: str,
    token_overrides: dict[str, Any],
) -> str:
    """Render safe CSS for a built-in style pack."""

    lines = [
        f'.reveal[data-visual-style="{style_id}"] {{',
        f"  --visual-style-pack: {pack_id};",
    ]
    for key in sorted(token_overrides):
        value = token_overrides[key]
        if value is None:
            continue
        css_key = str(key).replace("_", "-")
        css_value = str(value).replace("\n", " ").strip()
        if not css_value:
            continue
        lines.append(f"  --{css_key}: {css_value};")
    lines.append("}")
    return "\n".join(lines)
