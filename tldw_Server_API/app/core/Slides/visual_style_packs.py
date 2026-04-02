"""Reusable resolved appearance packs for built-in slide visual styles."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
import re
from pathlib import Path
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
_STYLE_PACKS_DIR = Path(__file__).resolve().parent / "style_packs"
_SAFE_TOKEN_KEY_PATTERN = re.compile(r"^[a-z0-9-]+$")
_SAFE_TOKEN_VALUE_PATTERN = re.compile(r"^[a-zA-Z0-9\s#(),.%'\"_/-]+$")


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


def _normalize_pack_id(pack_id: str) -> str | None:
    """Return a known pack identifier or ``None`` when the value is invalid."""

    normalized = str(pack_id).strip()
    if not normalized:
        return None
    if normalized not in _VISUAL_STYLE_PACKS_BY_ID:
        return None
    return normalized


@cache
def _load_pack_css(pack_id: str) -> str:
    """Read the static stylesheet for a built-in pack."""

    normalized_pack_id = _normalize_pack_id(pack_id)
    if normalized_pack_id is None:
        return ""

    packs_dir = _STYLE_PACKS_DIR.resolve()
    css_path = (packs_dir / f"{normalized_pack_id}.css").resolve()
    if css_path.parent != packs_dir:
        return ""
    if not css_path.exists():
        return ""
    return css_path.read_text(encoding="utf-8").strip()


def _normalize_token_key(value: Any) -> str | None:
    """Return a safe CSS custom property suffix or ``None`` when invalid."""

    normalized = str(value).strip().replace("_", "-").lower()
    if not normalized or not _SAFE_TOKEN_KEY_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _normalize_token_value(value: Any) -> str | None:
    """Return a safe CSS token value or ``None`` when it contains unsafe syntax."""

    normalized = str(value).replace("\n", " ").strip()
    if not normalized:
        return None
    lowered = normalized.lower()
    if "url(" in lowered or "@import" in lowered or "expression(" in lowered:
        return None
    if not _SAFE_TOKEN_VALUE_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _render_token_block(
    *,
    selector: str,
    pack_id: str,
    token_overrides: dict[str, Any],
) -> str:
    lines = [
        f"{selector} {{",
        f"  --visual-style-pack: {pack_id};",
    ]
    for key in sorted(token_overrides):
        value = token_overrides[key]
        if value is None:
            continue
        css_key = _normalize_token_key(key)
        css_value = _normalize_token_value(value)
        if css_key is None or css_value is None:
            continue
        lines.append(f"  --{css_key}: {css_value};")
    lines.append("}")
    return "\n".join(lines)


def render_pack_custom_css(
    *,
    style_id: str,
    pack_id: str,
    token_overrides: dict[str, Any],
) -> str:
    """Render safe CSS for a built-in style pack."""

    normalized_pack_id = _normalize_pack_id(pack_id)
    if normalized_pack_id is None:
        return ""

    parts = [
        _load_pack_css(normalized_pack_id),
        _render_token_block(
            selector=f'.reveal[data-style-pack="{normalized_pack_id}"]',
            pack_id=normalized_pack_id,
            token_overrides=token_overrides,
        ),
        _render_token_block(
            selector=f'.reveal[data-visual-style="{style_id}"]',
            pack_id=normalized_pack_id,
            token_overrides=token_overrides,
        ),
    ]
    return "\n\n".join(part for part in parts if part.strip())
