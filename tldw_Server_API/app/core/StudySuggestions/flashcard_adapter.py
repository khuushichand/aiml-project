"""Flashcard-specific suggestion context adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .types import SuggestionContext


def _copy_source_bundle(source_bundle: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(item) for item in (source_bundle or [])]


def is_source_grounded_session(session: Mapping[str, Any]) -> bool:
    source_bundle = session.get("source_bundle") or []
    if session.get("study_pack_id"):
        return True

    for item in source_bundle:
        if item.get("source_type") and item.get("source_id"):
            return True
        if item.get("citation_ordinal") is not None:
            return True
    return False


def build_flashcard_suggestion_context(session: Mapping[str, Any]) -> SuggestionContext:
    cards_reviewed = int(session.get("cards_reviewed") or 0)
    correct_count = int(session.get("correct_count") or 0)
    deck_id = int(session["deck_id"]) if session.get("deck_id") is not None else None
    grounded = is_source_grounded_session(session)
    review_mode = str(session.get("review_mode") or "")
    supports_source_aware_adjacency = grounded and review_mode != "manual"

    return SuggestionContext(
        service="flashcards",
        activity_type="flashcard_review_session",
        anchor_type="flashcard_review_session",
        anchor_id=int(session["id"]),
        workspace_id=session.get("workspace_id"),
        summary_metrics={
            "deck_id": deck_id,
            "cards_reviewed": cards_reviewed,
            "correct_count": correct_count,
        },
        performance_signals={
            "accuracy": (correct_count / cards_reviewed) if cards_reviewed else 0.0,
            "is_source_grounded_session": grounded,
            "supports_source_aware_adjacency": supports_source_aware_adjacency,
        },
        source_bundle=_copy_source_bundle(session.get("source_bundle")),
    )
