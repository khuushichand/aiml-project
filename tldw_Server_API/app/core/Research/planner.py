"""Planning helpers for deep research sessions."""

from __future__ import annotations

import re

from .models import ResearchPlan

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "external",
    "how",
    "local",
    "notes",
    "on",
    "sources",
    "the",
    "they",
    "web",
    "with",
}

_FALLBACK_FOCUS_AREAS = [
    "background and definitions",
    "supporting evidence",
    "contradictory evidence",
    "recency and trend validation",
    "source reliability review",
]


def _extract_keywords(query: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", query.lower())
    keywords: list[str] = []
    for token in tokens:
        if token in _STOPWORDS or len(token) < 4:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords


def build_initial_plan(*, query: str, source_policy: str, autonomy_mode: str) -> ResearchPlan:
    """Create a bounded first-pass plan for a research session."""
    keywords = _extract_keywords(query)
    focus_areas = [f"{keyword} evidence review" for keyword in keywords[:3]]
    for area in _FALLBACK_FOCUS_AREAS:
        if len(focus_areas) >= 5:
            break
        if area not in focus_areas:
            focus_areas.append(area)
    if len(focus_areas) < 3:
        focus_areas = _FALLBACK_FOCUS_AREAS[:3]

    return ResearchPlan(
        query=query,
        focus_areas=focus_areas[:7],
        source_policy=source_policy,
        autonomy_mode=autonomy_mode,
        stop_criteria={
            "min_cited_sections": 1,
            "max_iterations": 3,
            "require_contradiction_check": True,
        },
    )
