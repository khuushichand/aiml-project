"""Quiz-specific suggestion context adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .types import SuggestionContext


def _copy_source_bundle(source_bundle: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(item) for item in (source_bundle or [])]


def build_quiz_suggestion_context(
    *,
    quiz_attempt: Mapping[str, Any],
    source_bundle: Sequence[Mapping[str, Any]] | None = None,
) -> SuggestionContext:
    total_questions = int(quiz_attempt.get("total_questions") or 0)
    correct_answers = int(quiz_attempt.get("correct_answers") or 0)
    incorrect_count = sum(
        1 for result in quiz_attempt.get("question_results", []) if not result.get("correct", False)
    )
    accuracy = (correct_answers / total_questions) if total_questions else 0.0

    return SuggestionContext(
        service="quiz",
        activity_type="quiz_attempt",
        anchor_type="quiz_attempt",
        anchor_id=int(quiz_attempt["id"]),
        workspace_id=quiz_attempt.get("workspace_id"),
        summary_metrics={
            "score": int(quiz_attempt.get("score") or 0),
            "correct_answers": correct_answers,
            "total_questions": total_questions,
        },
        performance_signals={
            "incorrect_count": incorrect_count,
            "accuracy": accuracy,
        },
        source_bundle=_copy_source_bundle(source_bundle),
    )
