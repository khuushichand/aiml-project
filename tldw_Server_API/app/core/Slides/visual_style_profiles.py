"""Prompt profile definitions for built-in slide visual styles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualStyleProfile:
    """Reusable prompt guidance for a family of visual styles."""

    profile_id: str
    name: str
    guidance: tuple[str, ...]
    avoid: tuple[str, ...] = ()
    artifact_bias: tuple[str, ...] = ()


_VISUAL_STYLE_PROFILES: tuple[VisualStyleProfile, ...] = (
    VisualStyleProfile(
        profile_id="instructional_hand_drawn",
        name="Instructional Hand Drawn",
        guidance=(
            "prioritize pedagogical clarity",
            "use approachable explainer language",
            "keep the layout loose but readable",
        ),
        avoid=("overly polished corporate framing",),
        artifact_bias=("process_flow", "comparison_matrix"),
    ),
    VisualStyleProfile(
        profile_id="fine_art_human",
        name="Fine Art Human",
        guidance=(
            "lean into human texture and restraint",
            "use measured pacing and reflective language",
        ),
        avoid=("overly literal art direction",),
        artifact_bias=("timeline",),
    ),
    VisualStyleProfile(
        profile_id="tactile_playful",
        name="Tactile Playful",
        guidance=(
            "emphasize soft dimensionality and playful tactility",
            "keep the content grounded and easy to scan",
        ),
        avoid=("sharp technical jargon without explanation",),
        artifact_bias=("process_flow", "stat_group"),
    ),
    VisualStyleProfile(
        profile_id="technical_precision",
        name="Technical Precision",
        guidance=(
            "prefer exact sequencing and component naming",
            "foreground systems relationships over decoration",
        ),
        avoid=("decorative narrative filler",),
        artifact_bias=("process_flow", "comparison_matrix"),
    ),
    VisualStyleProfile(
        profile_id="metric_first",
        name="Metric First",
        guidance=(
            "foreground numbers, ratios, comparisons, and takeaways",
            "prefer concise analytical framing",
        ),
        avoid=("vague inspirational language",),
        artifact_bias=("stat_group", "comparison_matrix"),
    ),
    VisualStyleProfile(
        profile_id="narrative_journey",
        name="Narrative Journey",
        guidance=(
            "use a clear beginning, middle, and end",
            "treat the deck like a guided story arc",
        ),
        avoid=("disconnected bullet dumps",),
        artifact_bias=("timeline", "process_flow"),
    ),
    VisualStyleProfile(
        profile_id="corporate_strategy",
        name="Corporate Strategy",
        guidance=(
            "use concise executive framing",
            "connect problem, solution, and impact clearly",
        ),
        avoid=("fluffy brand language",),
        artifact_bias=("stat_group", "comparison_matrix"),
    ),
    VisualStyleProfile(
        profile_id="design_editorial",
        name="Design Editorial",
        guidance=(
            "use controlled whitespace and high-signal titles",
            "keep the language concise and considered",
        ),
        avoid=("bullet bloat",),
        artifact_bias=("comparison_matrix", "stat_group"),
    ),
    VisualStyleProfile(
        profile_id="playful_approachable",
        name="Playful Approachable",
        guidance=(
            "keep the tone friendly and accessible",
            "prefer warm, readable framing",
        ),
        avoid=("cold institutional wording",),
        artifact_bias=("process_flow", "stat_group"),
    ),
    VisualStyleProfile(
        profile_id="retro_synthetic",
        name="Retro Synthetic",
        guidance=(
            "use stylized framing language and strong section labels",
            "keep the content readable despite the theme",
        ),
        avoid=("overly modern corporate phrasing",),
        artifact_bias=("timeline", "process_flow"),
    ),
    VisualStyleProfile(
        profile_id="high_energy_marketing",
        name="High Energy Marketing",
        guidance=(
            "use sharp hooks and energetic pacing",
            "make the main takeaway obvious fast",
        ),
        avoid=("flat academic tone",),
        artifact_bias=("stat_group", "comparison_matrix"),
    ),
)

_VISUAL_STYLE_PROFILES_BY_ID = {profile.profile_id: profile for profile in _VISUAL_STYLE_PROFILES}


def _clone_profile(profile: VisualStyleProfile) -> VisualStyleProfile:
    """Return a defensive copy of a prompt profile."""

    return VisualStyleProfile(
        profile_id=profile.profile_id,
        name=profile.name,
        guidance=tuple(profile.guidance),
        avoid=tuple(profile.avoid),
        artifact_bias=tuple(profile.artifact_bias),
    )


def list_visual_style_profiles() -> list[VisualStyleProfile]:
    """Return all prompt profiles in catalog order."""

    return [_clone_profile(profile) for profile in _VISUAL_STYLE_PROFILES]


def get_visual_style_profile(profile_id: str) -> VisualStyleProfile | None:
    """Look up a prompt profile by identifier."""

    profile = _VISUAL_STYLE_PROFILES_BY_ID.get(profile_id)
    return _clone_profile(profile) if profile is not None else None


def build_prompt_profile_guidance(profile_id: str) -> tuple[str, ...]:
    """Return the guidance lines for a prompt profile."""

    profile = get_visual_style_profile(profile_id)
    if profile is None:
        return ()
    return profile.guidance
