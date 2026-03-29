"""Structured built-in visual style catalog for slide generation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BuiltinVisualStyleDefinition:
    """Structured catalog entry for a built-in slide visual style."""

    style_id: str
    name: str
    description: str
    category: str
    guide_number: int | None
    sort_order: int
    version: int
    prompt_profile: str
    style_pack: str
    style_pack_version: int
    base_theme: str
    generation_rules: dict[str, Any] = field(default_factory=dict)
    artifact_preferences: tuple[str, ...] = field(default_factory=tuple)
    fallback_policy: dict[str, Any] = field(default_factory=dict)
    appearance_overrides: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = field(default_factory=tuple)
    best_for: tuple[str, ...] = field(default_factory=tuple)


_CATEGORY_BEST_FOR: dict[str, tuple[str, ...]] = {
    "legacy": ("general slide generation",),
    "educational": ("teaching", "study notes"),
    "technical": ("systems explanation", "architecture walkthrough"),
    "narrative": ("story-led decks", "executive summaries"),
    "playful": ("lightweight explainer decks", "creative prompts"),
    "nostalgic": ("themed decks", "high-contrast storytelling"),
}


def _legacy_style_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "style_id": "infographic",
            "name": "Infographic",
            "description": "Digest-heavy slides with visual callouts and synthesis-first framing.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "corporate_strategy",
            "style_pack": "editorial_print",
            "base_theme": "white",
            "generation_rules": {"density": "medium", "bullet_bias": "low", "visual_callouts": "high"},
            "artifact_preferences": ("stat_group", "comparison_matrix", "process_flow"),
            "fallback_policy": {"mode": "textual-summary", "preserve_key_stats": True},
        },
        {
            "style_id": "minimal-academic",
            "name": "Minimal Academic",
            "description": "Calm, low-noise academic slides with restrained text and careful structure.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "design_editorial",
            "style_pack": "editorial_print",
            "base_theme": "white",
            "generation_rules": {"density": "low", "bullet_bias": "medium", "citation_bias": "high"},
            "artifact_preferences": ("comparison_matrix", "timeline"),
            "fallback_policy": {"mode": "outline", "preserve_key_stats": False},
        },
        {
            "style_id": "exam-focused-bullet",
            "name": "Exam-Focused Bullet",
            "description": "Recall-first slides optimized for high-yield revision and exam prep.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "technical_precision",
            "style_pack": "brutalist_editorial",
            "base_theme": "black",
            "generation_rules": {"density": "high", "bullet_bias": "high", "exam_focus": True},
            "artifact_preferences": ("stat_group", "comparison_matrix"),
            "fallback_policy": {"mode": "key-points", "preserve_key_stats": True},
        },
        {
            "style_id": "diagram-map-based",
            "name": "Diagram / Map-Based",
            "description": "Spatial and relationship-first slides with process and place emphasis.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "technical_precision",
            "style_pack": "technical_grid",
            "base_theme": "league",
            "generation_rules": {"density": "medium", "bullet_bias": "low", "spatial_reasoning": "high"},
            "artifact_preferences": ("process_flow", "comparison_matrix"),
            "fallback_policy": {"mode": "labeled-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "timeline",
            "name": "Timeline",
            "description": "Chronology-first slides focused on sequence, causality, and milestones.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "narrative_journey",
            "style_pack": "editorial_print",
            "base_theme": "beige",
            "generation_rules": {"density": "medium", "bullet_bias": "medium", "chronology_bias": "high"},
            "artifact_preferences": ("timeline", "stat_group"),
            "fallback_policy": {"mode": "ordered-bullets", "preserve_key_stats": True},
        },
        {
            "style_id": "data-visualization",
            "name": "Data Visualization",
            "description": "Trend and comparison slides that foreground metrics, ratios, and patterns.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "metric_first",
            "style_pack": "dashboard_glass",
            "base_theme": "night",
            "generation_rules": {"density": "medium", "bullet_bias": "low", "quant_focus": "high"},
            "artifact_preferences": ("stat_group", "comparison_matrix"),
            "fallback_policy": {"mode": "metric-summary", "preserve_key_stats": True},
        },
        {
            "style_id": "storytelling",
            "name": "Storytelling",
            "description": "Narrative slides with setup, tension, and payoff across the deck.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "narrative_journey",
            "style_pack": "editorial_print",
            "base_theme": "moon",
            "generation_rules": {"density": "medium", "bullet_bias": "low", "narrative_bias": "high"},
            "artifact_preferences": ("timeline", "process_flow"),
            "fallback_policy": {"mode": "narrative-outline", "preserve_key_stats": False},
        },
        {
            "style_id": "high-contrast-revision",
            "name": "High-Contrast Revision",
            "description": "Fast-scan revision slides using strong contrast and concise anchors.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "high_energy_marketing",
            "style_pack": "brutalist_editorial",
            "base_theme": "black",
            "generation_rules": {"density": "high", "bullet_bias": "high", "scanability": "high"},
            "artifact_preferences": ("stat_group", "process_flow"),
            "fallback_policy": {"mode": "flashcard-points", "preserve_key_stats": True},
        },
        {
            "style_id": "comparative-matrix",
            "name": "Comparative Matrix",
            "description": "Comparison-driven slides for similarities, differences, and tradeoffs.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "design_editorial",
            "style_pack": "editorial_print",
            "base_theme": "white",
            "generation_rules": {"density": "medium", "bullet_bias": "medium", "comparison_bias": "high"},
            "artifact_preferences": ("comparison_matrix", "stat_group"),
            "fallback_policy": {"mode": "two-column-summary", "preserve_key_stats": True},
        },
        {
            "style_id": "policy-case-brief",
            "name": "Policy / Case Brief",
            "description": "Issue, context, analysis, and takeaway framing for policy or case-study decks.",
            "category": "legacy",
            "guide_number": None,
            "prompt_profile": "corporate_strategy",
            "style_pack": "heritage_formal",
            "base_theme": "simple",
            "generation_rules": {"density": "medium", "bullet_bias": "medium", "argument_bias": "high"},
            "artifact_preferences": ("comparison_matrix", "timeline"),
            "fallback_policy": {"mode": "brief-outline", "preserve_key_stats": True},
        },
    )


def _notebooklm_style_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "style_id": "notebooklm-chalkboard",
            "name": "Chalkboard",
            "description": "Dark slate chalk style with instructional contrast.",
            "category": "educational",
            "guide_number": 1,
            "prompt_profile": "instructional_hand_drawn",
            "style_pack": "hand_drawn_surface",
            "base_theme": "black",
            "generation_rules": {"bullet_bias": "medium", "instructional_bias": "high"},
            "artifact_preferences": ("process_flow", "stat_group"),
            "appearance_overrides": {
                "token_overrides": {
                    "surface": "#0f172a",
                    "text": "#f8f2c8",
                    "accent": "#fef08a",
                    "border": "#f8f2c8",
                }
            },
            "fallback_policy": {"mode": "chalk-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-whiteboard",
            "name": "Whiteboard",
            "description": "Bright whiteboard framing with marker-like emphasis.",
            "category": "educational",
            "guide_number": 2,
            "prompt_profile": "instructional_hand_drawn",
            "style_pack": "hand_drawn_surface",
            "base_theme": "white",
            "generation_rules": {"bullet_bias": "medium", "instructional_bias": "high"},
            "artifact_preferences": ("process_flow", "comparison_matrix"),
            "appearance_overrides": {
                "token_overrides": {
                    "surface": "#fdfdfb",
                    "text": "#0f172a",
                    "accent": "#0f766e",
                    "border": "#d1d5db",
                }
            },
            "fallback_policy": {"mode": "marker-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-sketch-noting",
            "name": "Sketch Noting",
            "description": "Workshop synthesis style with loose annotated structure.",
            "category": "educational",
            "guide_number": 3,
            "prompt_profile": "instructional_hand_drawn",
            "style_pack": "hand_drawn_surface",
            "base_theme": "white",
            "generation_rules": {"bullet_bias": "medium", "instructional_bias": "high"},
            "artifact_preferences": ("process_flow", "comparison_matrix"),
            "appearance_overrides": {
                "token_overrides": {
                    "surface": "#fffaf0",
                    "text": "#374151",
                    "accent": "#d97706",
                    "border": "#fbbf24",
                }
            },
            "fallback_policy": {"mode": "sketch-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-graphite-charcoal",
            "name": "Graphite and Charcoal Realism",
            "description": "Monochrome realism with a restrained editorial mood.",
            "category": "educational",
            "guide_number": 4,
            "prompt_profile": "fine_art_human",
            "style_pack": "editorial_print",
            "base_theme": "serif",
            "generation_rules": {"bullet_bias": "low", "artful_recall": True},
            "artifact_preferences": ("timeline",),
            "fallback_policy": {"mode": "monochrome-outline", "preserve_key_stats": False},
        },
        {
            "style_id": "notebooklm-claymation",
            "name": "Claymation",
            "description": "Tactile, playful framing with soft dimensionality.",
            "category": "educational",
            "guide_number": 5,
            "prompt_profile": "tactile_playful",
            "style_pack": "tactile_soft",
            "base_theme": "beige",
            "generation_rules": {"bullet_bias": "medium", "playful_bias": True},
            "artifact_preferences": ("process_flow", "stat_group"),
            "fallback_policy": {"mode": "soft-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-exploded-view",
            "name": "Exploded View Diagram",
            "description": "Orthographic, assembly-first technical framing.",
            "category": "technical",
            "guide_number": 6,
            "prompt_profile": "technical_precision",
            "style_pack": "technical_grid",
            "base_theme": "simple",
            "generation_rules": {"bullet_bias": "low", "technical_bias": "high"},
            "artifact_preferences": ("process_flow", "comparison_matrix"),
            "fallback_policy": {"mode": "technical-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-blueprint",
            "name": "Blueprint",
            "description": "Cyan grid blueprint treatment with technical linework.",
            "category": "technical",
            "guide_number": 7,
            "prompt_profile": "technical_precision",
            "style_pack": "technical_grid",
            "base_theme": "night",
            "generation_rules": {"bullet_bias": "low", "technical_bias": "high"},
            "artifact_preferences": ("process_flow", "timeline"),
            "fallback_policy": {"mode": "technical-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-isometric-3d",
            "name": "Isometric 3D Illustration",
            "description": "Clean spatial framing with a corporate polish.",
            "category": "technical",
            "guide_number": 8,
            "prompt_profile": "technical_precision",
            "style_pack": "isometric_clean",
            "base_theme": "white",
            "generation_rules": {"bullet_bias": "low", "technical_bias": "high"},
            "artifact_preferences": ("process_flow", "stat_group"),
            "fallback_policy": {"mode": "spatial-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-minimalist-data-viz",
            "name": "Minimalist 2D Data-Viz",
            "description": "Flat quantitative clarity with editorial restraint.",
            "category": "technical",
            "guide_number": 9,
            "prompt_profile": "metric_first",
            "style_pack": "editorial_print",
            "base_theme": "white",
            "generation_rules": {"bullet_bias": "low", "quant_focus": "high"},
            "artifact_preferences": ("stat_group", "comparison_matrix"),
            "fallback_policy": {"mode": "metric-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-dark-saas-isometric",
            "name": "Dark-Mode SaaS Isometric",
            "description": "Dark module treatment with neon edges and product polish.",
            "category": "technical",
            "guide_number": 10,
            "prompt_profile": "technical_precision",
            "style_pack": "isometric_dark",
            "base_theme": "night",
            "generation_rules": {"bullet_bias": "low", "technical_bias": "high"},
            "artifact_preferences": ("process_flow", "stat_group"),
            "fallback_policy": {"mode": "spatial-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-professional-futuristic",
            "name": "Professional Futuristic",
            "description": "Premium future-tech framing with a dashboard feel.",
            "category": "technical",
            "guide_number": 11,
            "prompt_profile": "corporate_strategy",
            "style_pack": "dashboard_glass",
            "base_theme": "moon",
            "generation_rules": {"bullet_bias": "low", "quant_focus": "high"},
            "artifact_preferences": ("stat_group", "comparison_matrix"),
            "fallback_policy": {"mode": "futuristic-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-neumorphic",
            "name": "Neumorphic",
            "description": "Low-contrast tactile chrome with soft surfaces.",
            "category": "technical",
            "guide_number": 12,
            "prompt_profile": "corporate_strategy",
            "style_pack": "tactile_soft",
            "base_theme": "white",
            "generation_rules": {"bullet_bias": "low", "quant_focus": "medium"},
            "artifact_preferences": ("stat_group",),
            "fallback_policy": {"mode": "soft-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-high-contrast-monospace",
            "name": "High-Contrast Monospace",
            "description": "Terminal-style emphasis with bold contrast.",
            "category": "technical",
            "guide_number": 13,
            "prompt_profile": "technical_precision",
            "style_pack": "neon_cinematic",
            "base_theme": "black",
            "generation_rules": {"bullet_bias": "low", "scanability": "high"},
            "artifact_preferences": ("stat_group", "comparison_matrix"),
            "fallback_policy": {"mode": "terminal-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-journey-map",
            "name": "Conceptual Journey Map",
            "description": "Roadmap metaphor with a left-to-right narrative arc.",
            "category": "narrative",
            "guide_number": 14,
            "prompt_profile": "narrative_journey",
            "style_pack": "editorial_print",
            "base_theme": "beige",
            "generation_rules": {"bullet_bias": "medium", "narrative_bias": "high"},
            "artifact_preferences": ("timeline", "process_flow"),
            "fallback_policy": {"mode": "journey-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-strategic-infographic",
            "name": "Strategic Infographic",
            "description": "Problem-solution-impact framing for executive decks.",
            "category": "narrative",
            "guide_number": 15,
            "prompt_profile": "corporate_strategy",
            "style_pack": "editorial_print",
            "base_theme": "white",
            "generation_rules": {"bullet_bias": "low", "argument_bias": "high"},
            "artifact_preferences": ("stat_group", "comparison_matrix"),
            "fallback_policy": {"mode": "brief-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-executive-dashboard",
            "name": "Executive Dashboard",
            "description": "Dense KPI treatment with a dashboard cadence.",
            "category": "narrative",
            "guide_number": 16,
            "prompt_profile": "metric_first",
            "style_pack": "dashboard_glass",
            "base_theme": "night",
            "generation_rules": {"bullet_bias": "low", "quant_focus": "high"},
            "artifact_preferences": ("stat_group", "comparison_matrix"),
            "fallback_policy": {"mode": "dashboard-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-watercolour",
            "name": "Watercolour",
            "description": "Soft atmospheric palette for reflective storytelling.",
            "category": "narrative",
            "guide_number": 17,
            "prompt_profile": "narrative_journey",
            "style_pack": "editorial_print",
            "base_theme": "beige",
            "generation_rules": {"bullet_bias": "medium", "narrative_bias": "high"},
            "artifact_preferences": ("timeline",),
            "fallback_policy": {"mode": "soft-narrative-outline", "preserve_key_stats": False},
        },
        {
            "style_id": "notebooklm-heritage",
            "name": "Heritage",
            "description": "Formal institutional tone with historical gravity.",
            "category": "narrative",
            "guide_number": 18,
            "prompt_profile": "corporate_strategy",
            "style_pack": "heritage_formal",
            "base_theme": "serif",
            "generation_rules": {"bullet_bias": "medium", "argument_bias": "high"},
            "artifact_preferences": ("timeline", "comparison_matrix"),
            "fallback_policy": {"mode": "formal-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-swiss-design",
            "name": "Swiss Design",
            "description": "Strict grid and whitespace with editorial control.",
            "category": "narrative",
            "guide_number": 19,
            "prompt_profile": "design_editorial",
            "style_pack": "editorial_print",
            "base_theme": "white",
            "generation_rules": {"bullet_bias": "medium", "argument_bias": "high"},
            "artifact_preferences": ("comparison_matrix", "stat_group"),
            "fallback_policy": {"mode": "grid-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-glassmorphic-ui",
            "name": "Glass-morphic UI",
            "description": "Frosted panel treatment within sanitizer limits.",
            "category": "narrative",
            "guide_number": 20,
            "prompt_profile": "corporate_strategy",
            "style_pack": "dashboard_glass",
            "base_theme": "moon",
            "generation_rules": {"bullet_bias": "low", "quant_focus": "medium"},
            "artifact_preferences": ("stat_group",),
            "fallback_policy": {"mode": "glass-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-corporate-memphis",
            "name": "Corporate Memphis",
            "description": "Approachable startup tone with soft character framing.",
            "category": "narrative",
            "guide_number": 21,
            "prompt_profile": "playful_approachable",
            "style_pack": "pastel_character",
            "base_theme": "sky",
            "generation_rules": {"bullet_bias": "medium", "playful_bias": True},
            "artifact_preferences": ("process_flow", "stat_group"),
            "fallback_policy": {"mode": "approachable-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-papercraft",
            "name": "Papercraft",
            "description": "Layered shadows and paper-like depth.",
            "category": "playful",
            "guide_number": 22,
            "prompt_profile": "tactile_playful",
            "style_pack": "tactile_soft",
            "base_theme": "beige",
            "generation_rules": {"bullet_bias": "medium", "playful_bias": True},
            "artifact_preferences": ("process_flow",),
            "fallback_policy": {"mode": "paper-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-tactile-3d",
            "name": "Tactile 3D",
            "description": "Soft inflated UI style with tactile depth.",
            "category": "playful",
            "guide_number": 23,
            "prompt_profile": "tactile_playful",
            "style_pack": "tactile_soft",
            "base_theme": "white",
            "generation_rules": {"bullet_bias": "medium", "playful_bias": True},
            "artifact_preferences": ("stat_group",),
            "fallback_policy": {"mode": "soft-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-miniature-world",
            "name": "Miniature World",
            "description": "Toy-like overview framing with isometric cues.",
            "category": "playful",
            "guide_number": 24,
            "prompt_profile": "tactile_playful",
            "style_pack": "isometric_clean",
            "base_theme": "sky",
            "generation_rules": {"bullet_bias": "medium", "playful_bias": True},
            "artifact_preferences": ("process_flow", "timeline"),
            "fallback_policy": {"mode": "miniature-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-kawaii",
            "name": "Kawaii",
            "description": "Pastel rounded friendliness with a light narrative tone.",
            "category": "playful",
            "guide_number": 25,
            "prompt_profile": "playful_approachable",
            "style_pack": "pastel_character",
            "base_theme": "sky",
            "generation_rules": {"bullet_bias": "medium", "playful_bias": True},
            "artifact_preferences": ("process_flow", "stat_group"),
            "fallback_policy": {"mode": "cute-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-pop-art",
            "name": "Pop Art",
            "description": "High-contrast editorial framing with a bold commercial pulse.",
            "category": "nostalgic",
            "guide_number": 26,
            "prompt_profile": "high_energy_marketing",
            "style_pack": "editorial_print",
            "base_theme": "white",
            "generation_rules": {"bullet_bias": "medium", "energy_bias": "high"},
            "artifact_preferences": ("stat_group",),
            "fallback_policy": {"mode": "pop-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-risograph-print",
            "name": "Risograph Print",
            "description": "Grainy spot-color editorial look.",
            "category": "nostalgic",
            "guide_number": 27,
            "prompt_profile": "design_editorial",
            "style_pack": "editorial_print",
            "base_theme": "beige",
            "generation_rules": {"bullet_bias": "medium", "energy_bias": "medium"},
            "artifact_preferences": ("comparison_matrix", "stat_group"),
            "fallback_policy": {"mode": "print-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-retro-90s-gaming",
            "name": "Retro 90s Gaming",
            "description": "Chunky UI and low-poly flavor with a retro synthetic tone.",
            "category": "nostalgic",
            "guide_number": 28,
            "prompt_profile": "retro_synthetic",
            "style_pack": "retro_pixel",
            "base_theme": "black",
            "generation_rules": {"bullet_bias": "medium", "retro_bias": "high"},
            "artifact_preferences": ("process_flow", "stat_group"),
            "fallback_policy": {"mode": "retro-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-oregon-trail",
            "name": "Oregon Trail",
            "description": "8-bit frontier journey framing.",
            "category": "nostalgic",
            "guide_number": 29,
            "prompt_profile": "retro_synthetic",
            "style_pack": "retro_pixel",
            "base_theme": "simple",
            "generation_rules": {"bullet_bias": "medium", "retro_bias": "high"},
            "artifact_preferences": ("timeline", "process_flow"),
            "fallback_policy": {"mode": "journey-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-cyberpunk",
            "name": "Cyberpunk",
            "description": "Neon, gritty, and atmospheric with strong contrast.",
            "category": "nostalgic",
            "guide_number": 30,
            "prompt_profile": "high_energy_marketing",
            "style_pack": "neon_cinematic",
            "base_theme": "blood",
            "generation_rules": {"bullet_bias": "low", "energy_bias": "high"},
            "artifact_preferences": ("stat_group", "comparison_matrix"),
            "fallback_policy": {"mode": "neon-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-anime-battle",
            "name": "Anime Battle",
            "description": "High-energy launch and competition framing.",
            "category": "nostalgic",
            "guide_number": 31,
            "prompt_profile": "high_energy_marketing",
            "style_pack": "neon_cinematic",
            "base_theme": "moon",
            "generation_rules": {"bullet_bias": "medium", "energy_bias": "high"},
            "artifact_preferences": ("process_flow", "stat_group"),
            "fallback_policy": {"mode": "battle-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-anime",
            "name": "Anime",
            "description": "Bright cinematic narrative tone with approachable energy.",
            "category": "nostalgic",
            "guide_number": 32,
            "prompt_profile": "playful_approachable",
            "style_pack": "pastel_character",
            "base_theme": "sky",
            "generation_rules": {"bullet_bias": "medium", "energy_bias": "medium"},
            "artifact_preferences": ("timeline", "process_flow"),
            "fallback_policy": {"mode": "cinematic-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-retro-print",
            "name": "Retro Print",
            "description": "Archive or newspaper tone with editorial restraint.",
            "category": "nostalgic",
            "guide_number": 33,
            "prompt_profile": "design_editorial",
            "style_pack": "editorial_print",
            "base_theme": "beige",
            "generation_rules": {"bullet_bias": "medium", "energy_bias": "medium"},
            "artifact_preferences": ("timeline", "comparison_matrix"),
            "fallback_policy": {"mode": "archive-outline", "preserve_key_stats": True},
        },
        {
            "style_id": "notebooklm-brutalist-design",
            "name": "Brutalist Design",
            "description": "Harsh contrast and oversized type with editorial edge.",
            "category": "nostalgic",
            "guide_number": 34,
            "prompt_profile": "design_editorial",
            "style_pack": "brutalist_editorial",
            "base_theme": "simple",
            "generation_rules": {"bullet_bias": "medium", "energy_bias": "high"},
            "artifact_preferences": ("comparison_matrix", "stat_group"),
            "fallback_policy": {"mode": "brutalist-outline", "preserve_key_stats": True},
        },
    )


def _build_definition(spec: dict[str, Any], *, sort_order: int) -> BuiltinVisualStyleDefinition:
    category = str(spec["category"])
    return BuiltinVisualStyleDefinition(
        style_id=str(spec["style_id"]),
        name=str(spec["name"]),
        description=str(spec["description"]),
        category=category,
        guide_number=spec.get("guide_number"),
        sort_order=sort_order,
        version=1,
        prompt_profile=str(spec["prompt_profile"]),
        style_pack=str(spec["style_pack"]),
        style_pack_version=1,
        base_theme=str(spec["base_theme"]),
        generation_rules=deepcopy(spec.get("generation_rules") or {}),
        artifact_preferences=tuple(str(item) for item in spec.get("artifact_preferences") or ()),
        fallback_policy=deepcopy(spec.get("fallback_policy") or {}),
        appearance_overrides=deepcopy(spec.get("appearance_overrides") or {}),
        tags=(
            category,
            str(spec["style_pack"]),
            str(spec["prompt_profile"]),
        ),
        best_for=_CATEGORY_BEST_FOR.get(category, ("slide generation",)),
    )


_BUILTIN_STYLE_DEFINITIONS: tuple[BuiltinVisualStyleDefinition, ...] = tuple(
    _build_definition(spec, sort_order=index)
    for index, spec in enumerate((*_legacy_style_specs(), *_notebooklm_style_specs()), start=1)
)

_BUILTIN_STYLE_DEFINITIONS_BY_ID = {definition.style_id: definition for definition in _BUILTIN_STYLE_DEFINITIONS}


def _clone_definition(definition: BuiltinVisualStyleDefinition) -> BuiltinVisualStyleDefinition:
    """Return a defensive copy of a built-in style definition."""

    return BuiltinVisualStyleDefinition(
        style_id=definition.style_id,
        name=definition.name,
        description=definition.description,
        category=definition.category,
        guide_number=definition.guide_number,
        sort_order=definition.sort_order,
        version=definition.version,
        prompt_profile=definition.prompt_profile,
        style_pack=definition.style_pack,
        style_pack_version=definition.style_pack_version,
        base_theme=definition.base_theme,
        generation_rules=deepcopy(definition.generation_rules),
        artifact_preferences=tuple(definition.artifact_preferences),
        fallback_policy=deepcopy(definition.fallback_policy),
        appearance_overrides=deepcopy(definition.appearance_overrides),
        tags=tuple(definition.tags),
        best_for=tuple(definition.best_for),
    )


def _validate_registry_integrity() -> None:
    """Ensure catalog entries reference valid profile and pack identifiers."""

    from tldw_Server_API.app.core.Slides.visual_style_packs import get_visual_style_pack
    from tldw_Server_API.app.core.Slides.visual_style_profiles import get_visual_style_profile

    missing_profiles = sorted(
        {
            definition.prompt_profile
            for definition in _BUILTIN_STYLE_DEFINITIONS
            if get_visual_style_profile(definition.prompt_profile) is None
        }
    )
    missing_packs = sorted(
        {
            definition.style_pack
            for definition in _BUILTIN_STYLE_DEFINITIONS
            if get_visual_style_pack(definition.style_pack) is None
        }
    )
    if missing_profiles or missing_packs:
        problems: list[str] = []
        if missing_profiles:
            problems.append(f"missing prompt profiles: {', '.join(missing_profiles)}")
        if missing_packs:
            problems.append(f"missing style packs: {', '.join(missing_packs)}")
        raise RuntimeError("invalid visual style registry: " + "; ".join(problems))


def list_builtin_visual_style_definitions() -> list[BuiltinVisualStyleDefinition]:
    """Return all built-in style definitions in registry order."""

    return [_clone_definition(definition) for definition in _BUILTIN_STYLE_DEFINITIONS]


def get_builtin_visual_style_definition(style_id: str) -> BuiltinVisualStyleDefinition | None:
    """Look up a built-in style definition by identifier."""

    definition = _BUILTIN_STYLE_DEFINITIONS_BY_ID.get(style_id)
    return _clone_definition(definition) if definition is not None else None


_validate_registry_integrity()
