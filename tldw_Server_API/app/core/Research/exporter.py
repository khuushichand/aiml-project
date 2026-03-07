"""Helpers for packaging final deep research outputs."""

from __future__ import annotations

from typing import Any


def build_final_package(
    *,
    brief: dict[str, Any],
    outline: dict[str, Any],
    report_markdown: str,
    claims: list[dict[str, Any]],
    source_inventory: list[dict[str, Any]],
    unresolved_questions: list[str] | None = None,
) -> dict[str, Any]:
    """Build the canonical deep research package and enforce citation coverage."""
    query = str(brief.get("query") or "").strip()
    if not query:
        raise ValueError("brief_missing_query")
    if not report_markdown.strip():
        raise ValueError("report_missing")

    for claim in claims:
        citations = claim.get("citations") or []
        if not citations:
            raise ValueError("claim_missing_citations")

    return {
        "question": query,
        "brief": dict(brief),
        "outline": dict(outline),
        "report_markdown": report_markdown,
        "claims": list(claims),
        "source_inventory": list(source_inventory),
        "unresolved_questions": list(unresolved_questions or []),
    }


__all__ = ["build_final_package"]
