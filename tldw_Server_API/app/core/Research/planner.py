"""Planning helpers for deep research sessions."""

from __future__ import annotations

import re
from typing import Any

from .models import ResearchPlan

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "attached",
    "about",
    "conclude",
    "concluded",
    "did",
    "external",
    "how",
    "local",
    "notes",
    "on",
    "next",
    "research",
    "sources",
    "the",
    "they",
    "should",
    "web",
    "with",
    "what",
    "would",
    "could",
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


def _extract_follow_up_keywords(follow_up_background: dict[str, Any]) -> list[str]:
    texts: list[str] = []

    key_claims = follow_up_background.get("key_claims")
    if isinstance(key_claims, list):
        for claim in key_claims:
            if not isinstance(claim, dict):
                continue
            claim_text = claim.get("text")
            if isinstance(claim_text, str):
                texts.append(claim_text)

    unresolved_questions = follow_up_background.get("unresolved_questions")
    if isinstance(unresolved_questions, list):
        for entry in unresolved_questions:
            if isinstance(entry, str):
                texts.append(entry)

    outline = follow_up_background.get("outline")
    if isinstance(outline, list):
        for item in outline:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            focus_area = item.get("focus_area")
            if isinstance(title, str):
                texts.append(title)
            if isinstance(focus_area, str):
                texts.append(focus_area)

    question = follow_up_background.get("question")
    if isinstance(question, str):
        texts.append(question)

    keywords: list[str] = []
    for text in texts:
        for keyword in _extract_keywords(text):
            if keyword not in keywords:
                keywords.append(keyword)
    return keywords


def build_initial_plan(
    *,
    query: str,
    source_policy: str,
    autonomy_mode: str,
    follow_up_background: dict[str, Any] | None = None,
) -> ResearchPlan:
    """Create a bounded first-pass plan for a research session."""
    keywords = _extract_keywords(query)
    focus_areas = [f"{keyword} evidence review" for keyword in keywords[:3]]
    if follow_up_background:
        background_keywords = _extract_follow_up_keywords(follow_up_background)
        for keyword in background_keywords[:3]:
            area = f"{keyword} follow-up review"
            if area not in focus_areas:
                focus_areas.append(area)
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
