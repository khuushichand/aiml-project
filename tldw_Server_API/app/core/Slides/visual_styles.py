"""Built-in visual style presets for slide generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VisualStylePreset:
    """Resolved built-in visual style definition."""

    style_id: str
    name: str
    description: str
    version: int
    generation_rules: dict[str, Any]
    artifact_preferences: tuple[str, ...]
    appearance_defaults: dict[str, Any]
    fallback_policy: dict[str, Any]


_BUILTIN_VISUAL_STYLES: tuple[VisualStylePreset, ...] = (
    VisualStylePreset(
        style_id="infographic",
        name="Infographic",
        description="Digest-heavy slides with visual callouts and synthesis-first framing.",
        version=1,
        generation_rules={"density": "medium", "bullet_bias": "low", "visual_callouts": "high"},
        artifact_preferences=("stat_group", "comparison_matrix", "process_flow"),
        appearance_defaults={"theme": "white"},
        fallback_policy={"mode": "textual-summary", "preserve_key_stats": True},
    ),
    VisualStylePreset(
        style_id="minimal-academic",
        name="Minimal Academic",
        description="Calm, low-noise academic slides with restrained text and careful structure.",
        version=1,
        generation_rules={"density": "low", "bullet_bias": "medium", "citation_bias": "high"},
        artifact_preferences=("comparison_matrix", "timeline"),
        appearance_defaults={"theme": "white"},
        fallback_policy={"mode": "outline", "preserve_key_stats": False},
    ),
    VisualStylePreset(
        style_id="exam-focused-bullet",
        name="Exam-Focused Bullet",
        description="Recall-first slides optimized for high-yield revision and exam prep.",
        version=1,
        generation_rules={"density": "high", "bullet_bias": "high", "exam_focus": True},
        artifact_preferences=("stat_group", "comparison_matrix"),
        appearance_defaults={"theme": "black"},
        fallback_policy={"mode": "key-points", "preserve_key_stats": True},
    ),
    VisualStylePreset(
        style_id="diagram-map-based",
        name="Diagram / Map-Based",
        description="Spatial and relationship-first slides with process and place emphasis.",
        version=1,
        generation_rules={"density": "medium", "bullet_bias": "low", "spatial_reasoning": "high"},
        artifact_preferences=("process_flow", "comparison_matrix"),
        appearance_defaults={"theme": "league"},
        fallback_policy={"mode": "labeled-outline", "preserve_key_stats": True},
    ),
    VisualStylePreset(
        style_id="timeline",
        name="Timeline",
        description="Chronology-first slides focused on sequence, causality, and milestones.",
        version=1,
        generation_rules={"density": "medium", "bullet_bias": "medium", "chronology_bias": "high"},
        artifact_preferences=("timeline", "stat_group"),
        appearance_defaults={"theme": "beige"},
        fallback_policy={"mode": "ordered-bullets", "preserve_key_stats": True},
    ),
    VisualStylePreset(
        style_id="data-visualization",
        name="Data Visualization",
        description="Trend and comparison slides that foreground metrics, ratios, and patterns.",
        version=1,
        generation_rules={"density": "medium", "bullet_bias": "low", "quant_focus": "high"},
        artifact_preferences=("stat_group", "comparison_matrix"),
        appearance_defaults={"theme": "night"},
        fallback_policy={"mode": "metric-summary", "preserve_key_stats": True},
    ),
    VisualStylePreset(
        style_id="storytelling",
        name="Storytelling",
        description="Narrative slides with setup, tension, and payoff across the deck.",
        version=1,
        generation_rules={"density": "medium", "bullet_bias": "low", "narrative_bias": "high"},
        artifact_preferences=("timeline", "process_flow"),
        appearance_defaults={"theme": "moon"},
        fallback_policy={"mode": "narrative-outline", "preserve_key_stats": False},
    ),
    VisualStylePreset(
        style_id="high-contrast-revision",
        name="High-Contrast Revision",
        description="Fast-scan revision slides using strong contrast and concise anchors.",
        version=1,
        generation_rules={"density": "high", "bullet_bias": "high", "scanability": "high"},
        artifact_preferences=("stat_group", "process_flow"),
        appearance_defaults={"theme": "black"},
        fallback_policy={"mode": "flashcard-points", "preserve_key_stats": True},
    ),
    VisualStylePreset(
        style_id="comparative-matrix",
        name="Comparative Matrix",
        description="Comparison-driven slides for similarities, differences, and tradeoffs.",
        version=1,
        generation_rules={"density": "medium", "bullet_bias": "medium", "comparison_bias": "high"},
        artifact_preferences=("comparison_matrix", "stat_group"),
        appearance_defaults={"theme": "white"},
        fallback_policy={"mode": "two-column-summary", "preserve_key_stats": True},
    ),
    VisualStylePreset(
        style_id="policy-case-brief",
        name="Policy / Case Brief",
        description="Issue, context, analysis, and takeaway framing for policy or case-study decks.",
        version=1,
        generation_rules={"density": "medium", "bullet_bias": "medium", "argument_bias": "high"},
        artifact_preferences=("comparison_matrix", "timeline"),
        appearance_defaults={"theme": "simple"},
        fallback_policy={"mode": "brief-outline", "preserve_key_stats": True},
    ),
)


def list_builtin_visual_styles() -> list[VisualStylePreset]:
    """Return all built-in visual style presets."""

    return list(_BUILTIN_VISUAL_STYLES)


def get_builtin_visual_style(style_id: str) -> VisualStylePreset | None:
    """Look up a built-in visual style by identifier."""

    for style in _BUILTIN_VISUAL_STYLES:
        if style.style_id == style_id:
            return style
    return None
