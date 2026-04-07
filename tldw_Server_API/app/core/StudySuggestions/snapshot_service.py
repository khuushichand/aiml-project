"""Snapshot helpers for shared study-suggestion status and refresh flows."""

from __future__ import annotations

import contextlib
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB, ConflictError
from tldw_Server_API.app.core.Jobs.manager import JobManager

from .flashcard_adapter import build_flashcard_suggestion_context
from .jobs import (
    STUDY_SUGGESTIONS_DOMAIN,
    STUDY_SUGGESTIONS_REFRESH_JOB_TYPE,
    study_suggestions_jobs_queue,
)
from .quiz_adapter import build_quiz_suggestion_context
from .topic_pipeline import rank_suggestion_topics, resolve_topic_candidates


def _safe_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _titleize_label(label: str) -> str:
    words = [part for part in str(label or "").strip().split() if part]
    if not words:
        return "Review"
    return " ".join(word.capitalize() for word in words)


def _unique_preserve(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = _safe_text(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return ordered


def _unique_sources(values: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str | None]] = set()
    ordered: list[dict[str, str]] = []
    for value in values:
        source_type = _safe_text(value.get("source_type"))
        source_id = _safe_text(value.get("source_id"))
        label = _safe_text(value.get("label"))
        if not source_type or not source_id:
            continue
        key = (source_type.casefold(), source_id.casefold(), label.casefold() if label else None)
        if key in seen:
            continue
        seen.add(key)
        item = {
            "source_type": source_type,
            "source_id": source_id,
        }
        if label:
            item["label"] = label
        ordered.append(item)
    return ordered


def _normalize_citation_source(citation: Mapping[str, Any]) -> dict[str, str] | None:
    source_type = _safe_text(citation.get("source_type"))
    source_id = _safe_text(citation.get("source_id"))
    label = _safe_text(citation.get("label"))
    if not source_type or not source_id:
        return None
    source: dict[str, str] = {
        "source_type": source_type,
        "source_id": source_id,
    }
    if label:
        source["label"] = label
    return source


def _extract_quiz_labels(
    attempt: Mapping[str, Any],
) -> tuple[list[str], list[str], list[str], list[str], list[str], list[dict[str, str]]]:
    questions = attempt.get("questions") or []
    answers = attempt.get("answers") or []
    answers_by_question_id = {
        int(answer["question_id"]): answer
        for answer in answers
        if isinstance(answer, Mapping) and answer.get("question_id") is not None
    }

    source_labels: list[str] = []
    tag_labels: list[str] = []
    weakness_labels: list[str] = []
    adjacent_labels: list[str] = []
    source_bundle: list[dict[str, str]] = []

    for question in questions:
        if not isinstance(question, Mapping):
            continue
        question_id = question.get("id")
        answer = answers_by_question_id.get(int(question_id)) if question_id is not None else None
        question_tags = [tag for tag in (question.get("tags") or []) if _safe_text(tag)]
        citations = [item for item in (question.get("source_citations") or []) if isinstance(item, Mapping)]
        citation_labels = [_safe_text(citation.get("label")) for citation in citations]
        citation_labels = [label for label in citation_labels if label]

        tag_labels.extend(question_tags)
        source_labels.extend(citation_labels)
        for citation in citations:
            source = _normalize_citation_source(citation)
            if source:
                source_bundle.append(source)

        is_incorrect = bool(answer) and answer.get("is_correct") is False
        target = weakness_labels if is_incorrect else adjacent_labels
        target.extend(question_tags)
        target.extend(citation_labels)

    derived_labels = []
    if not source_labels and not tag_labels:
        incorrect_count = sum(1 for answer in answers if isinstance(answer, Mapping) and answer.get("is_correct") is False)
        derived_labels.append("missed questions" if incorrect_count else "review")

    return (
        _unique_preserve(source_labels),
        _unique_preserve(tag_labels),
        _unique_preserve(derived_labels),
        _unique_preserve(weakness_labels),
        _unique_preserve(adjacent_labels),
        _unique_sources(source_bundle),
    )


def _find_quiz_topic_source(
    canonical_label: str,
    source_bundle: list[dict[str, str]],
) -> dict[str, str] | None:
    for source in source_bundle:
        source_label = _safe_text(source.get("label"))
        if source_label and source_label.casefold() == canonical_label.casefold():
            return source
    return source_bundle[0] if source_bundle else None


def _build_quiz_snapshot_payload(note_db: CharactersRAGDB, anchor_id: int) -> tuple[str, str, dict[str, Any]]:
    attempt = note_db.get_attempt(anchor_id, include_questions=True, include_answers=True)
    if not attempt:
        raise ConflictError("Attempt not found", entity="quiz_attempts", identifier=anchor_id)  # noqa: TRY003

    answers = [answer for answer in (attempt.get("answers") or []) if isinstance(answer, Mapping)]
    questions = [question for question in (attempt.get("questions") or []) if isinstance(question, Mapping)]
    correct_answers = sum(1 for answer in answers if answer.get("is_correct") is True)
    question_results = [
        {
            "question_id": answer.get("question_id"),
            "correct": bool(answer.get("is_correct")),
        }
        for answer in answers
    ]
    source_labels, tag_labels, derived_labels, weakness_labels, adjacent_labels, source_bundle = _extract_quiz_labels(attempt)
    context = build_quiz_suggestion_context(
        quiz_attempt={
            "id": int(attempt["id"]),
            "quiz_id": int(attempt["quiz_id"]),
            "workspace_id": attempt.get("workspace_id"),
            "score": int(attempt.get("score") or 0),
            "correct_answers": correct_answers,
            "total_questions": len(questions),
            "question_results": question_results,
        },
        source_bundle=source_bundle,
    )
    candidates = resolve_topic_candidates(
        source_labels=source_labels,
        tag_labels=tag_labels,
        derived_labels=derived_labels,
    )
    ranked_topics = rank_suggestion_topics(
        candidates,
        weakness_labels=weakness_labels,
        adjacent_labels=adjacent_labels,
        exploratory_labels=derived_labels,
    )
    topics: list[dict[str, Any]] = []
    for index, topic in enumerate(ranked_topics[:6], start=1):
        source = _find_quiz_topic_source(topic.canonical_label, context.source_bundle)
        raw_label = topic.raw_labels[0] if topic.raw_labels else topic.canonical_label
        item: dict[str, Any] = {
            "id": f"topic-{index}",
            "display_label": _titleize_label(raw_label),
            "type": topic.evidence_class,
            "status": topic.rank_reason,
            "selected": topic.rank_reason == "weakness",
        }
        if source:
            item["source_type"] = source["source_type"]
            item["source_id"] = source["source_id"]
        topics.append(item)

    if not topics:
        topics.append(
            {
                "id": "topic-1",
                "display_label": "Review",
                "type": "derived",
                "status": "candidate",
                "selected": False,
            }
        )

    payload = {
        "summary": {
            "score": int(context.summary_metrics.get("score") or 0),
            "correct_count": int(context.summary_metrics.get("correct_answers") or 0),
            "total_count": int(context.summary_metrics.get("total_questions") or 0),
        },
        "counts": {
            "topic_count": len(topics),
        },
        "topics": topics,
    }
    return context.service, context.activity_type, payload


def _build_flashcard_snapshot_payload(note_db: CharactersRAGDB, anchor_id: int) -> tuple[str, str, dict[str, Any]]:
    session = note_db.get_flashcard_review_session(int(anchor_id))
    if not session:
        raise ConflictError("Flashcard review session not found", entity="flashcard_review_sessions", identifier=anchor_id)  # noqa: TRY003

    context = build_flashcard_suggestion_context(
        {
            **session,
            "cards_reviewed": 0,
            "correct_count": 0,
            "source_bundle": [],
        }
    )
    derived_labels = []
    if session.get("tag_filter"):
        derived_labels.append(str(session["tag_filter"]))
    if session.get("deck_id"):
        deck = note_db.get_deck(int(session["deck_id"]))
        if deck and deck.get("name"):
            derived_labels.append(str(deck["name"]))
    if not derived_labels:
        derived_labels.append("spaced repetition")

    candidates = resolve_topic_candidates(
        source_labels=[],
        tag_labels=[session["tag_filter"]] if session.get("tag_filter") else [],
        derived_labels=derived_labels,
    )
    ranked_topics = rank_suggestion_topics(
        candidates,
        weakness_labels=[],
        adjacent_labels=[session["tag_filter"]] if session.get("tag_filter") else [],
        exploratory_labels=derived_labels,
    )
    topics = [
        {
            "id": f"topic-{index}",
            "display_label": _titleize_label(topic.raw_labels[0] if topic.raw_labels else topic.canonical_label),
            "type": topic.evidence_class,
            "status": topic.rank_reason,
            "selected": topic.rank_reason == "adjacent",
        }
        for index, topic in enumerate(ranked_topics[:4], start=1)
    ]
    payload = {
        "summary": {
            "deck_id": context.summary_metrics.get("deck_id"),
            "correct_count": 0,
            "total_count": 0,
        },
        "counts": {
            "topic_count": len(topics),
        },
        "topics": topics,
    }
    return context.service, context.activity_type, payload


def _build_snapshot_payload(note_db: CharactersRAGDB, anchor_type: str, anchor_id: int) -> tuple[str, str, dict[str, Any]]:
    normalized_anchor_type = str(anchor_type or "").strip().lower()
    if normalized_anchor_type == "quiz_attempt":
        return _build_quiz_snapshot_payload(note_db, int(anchor_id))
    if normalized_anchor_type == "flashcard_review_session":
        return _build_flashcard_snapshot_payload(note_db, int(anchor_id))
    raise ValueError("unsupported_study_suggestions_anchor_type")


def _job_matches_anchor(job: Mapping[str, Any], *, anchor_type: str, anchor_id: int) -> bool:
    payload = job.get("payload") or {}
    return (
        str(payload.get("anchor_type") or "").strip().lower() == str(anchor_type or "").strip().lower()
        and int(payload.get("anchor_id") or 0) == int(anchor_id)
    )


def _parse_job_created_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    with contextlib.suppress(ValueError):
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        with contextlib.suppress(ValueError):
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
    return None


def _find_matching_job(
    *,
    job_manager: JobManager,
    anchor_type: str,
    anchor_id: int,
    statuses: Iterable[str],
    owner_user_id: str | None = None,
) -> dict[str, Any] | None:
    page_size = 100
    for status in statuses:
        created_before = None
        before_id = None
        while True:
            jobs = job_manager.list_jobs(
                domain=STUDY_SUGGESTIONS_DOMAIN,
                queue=study_suggestions_jobs_queue(),
                status=status,
                owner_user_id=owner_user_id,
                job_type=STUDY_SUGGESTIONS_REFRESH_JOB_TYPE,
                created_before=created_before,
                before_id=before_id,
                limit=page_size,
            )
            if not jobs:
                break
            for job in jobs:
                if _job_matches_anchor(job, anchor_type=anchor_type, anchor_id=anchor_id):
                    return job
            if len(jobs) < page_size:
                break
            last_job = jobs[-1]
            created_before = _parse_job_created_at(last_job.get("created_at"))
            if created_before is None:
                break
            before_id = int(last_job["id"])
    return None


def get_anchor_status(
    *,
    note_db: CharactersRAGDB,
    job_manager: JobManager,
    anchor_type: str,
    anchor_id: int,
    owner_user_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the current suggestion status for a concrete anchor."""

    anchor_id = int(anchor_id)
    pending_job = _find_matching_job(
        job_manager=job_manager,
        anchor_type=anchor_type,
        anchor_id=anchor_id,
        statuses=("processing", "queued"),
        owner_user_id=owner_user_id,
    )
    if pending_job:
        return {
            "anchor_type": anchor_type,
            "anchor_id": anchor_id,
            "status": "pending",
            "job_id": int(pending_job["id"]),
            "snapshot_id": None,
        }

    failed_job = _find_matching_job(
        job_manager=job_manager,
        anchor_type=anchor_type,
        anchor_id=anchor_id,
        statuses=("failed",),
        owner_user_id=owner_user_id,
    )
    if failed_job:
        return {
            "anchor_type": anchor_type,
            "anchor_id": anchor_id,
            "status": "failed",
            "job_id": int(failed_job["id"]),
            "snapshot_id": None,
        }

    snapshots = note_db.list_suggestion_snapshots_for_anchor(anchor_type, anchor_id)
    active_snapshot = next((row for row in snapshots if str(row.get("status") or "").strip().lower() == "active"), None)
    if active_snapshot:
        return {
            "anchor_type": anchor_type,
            "anchor_id": anchor_id,
            "status": "ready",
            "job_id": None,
            "snapshot_id": int(active_snapshot["id"]),
        }

    return {
        "anchor_type": anchor_type,
        "anchor_id": anchor_id,
        "status": "none",
        "job_id": None,
        "snapshot_id": None,
    }


def load_live_evidence_for_snapshot(
    snapshot_row: Mapping[str, Any],
    *,
    note_db: CharactersRAGDB,
    principal: AuthPrincipal,
) -> dict[str, Any]:
    """Hydrate best-effort live evidence for a stored snapshot."""

    _ = principal
    payload = snapshot_row.get("payload_json") or {}
    topics = payload.get("topics") if isinstance(payload, Mapping) else []
    if not isinstance(topics, list):
        return {}

    live_evidence: dict[str, Any] = {}
    for index, topic in enumerate(topics, start=1):
        if not isinstance(topic, Mapping):
            continue
        topic_id = _safe_text(topic.get("id")) or f"topic-{index}"
        source_type = _safe_text(topic.get("source_type"))
        source_id = _safe_text(topic.get("source_id"))
        item: dict[str, Any] = {
            "source_available": bool(source_type and source_id),
        }
        if source_type:
            item["source_type"] = source_type
        if source_id:
            item["source_id"] = source_id
        live_evidence[topic_id] = item
    return live_evidence


def serialize_snapshot(snapshot_row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize DB column names for API responses."""

    return {
        "id": int(snapshot_row["id"]),
        "service": snapshot_row["service"],
        "activity_type": snapshot_row["activity_type"],
        "anchor_type": snapshot_row["anchor_type"],
        "anchor_id": int(snapshot_row["anchor_id"]),
        "suggestion_type": snapshot_row["suggestion_type"],
        "status": snapshot_row["status"],
        "payload": snapshot_row.get("payload_json"),
        "user_selection": snapshot_row.get("user_selection_json"),
        "refreshed_from_snapshot_id": snapshot_row.get("refreshed_from_snapshot_id"),
        "created_at": snapshot_row.get("created_at"),
        "last_modified": snapshot_row.get("last_modified"),
    }


def refresh_snapshot_for_anchor(
    *,
    note_db: CharactersRAGDB,
    anchor_type: str,
    anchor_id: int,
    refreshed_from_snapshot_id: int | None = None,
    principal: AuthPrincipal,
) -> int:
    """Create a fresh snapshot for the provided anchor."""

    _ = principal
    service, activity_type, payload = _build_snapshot_payload(note_db, anchor_type, int(anchor_id))
    return note_db.create_suggestion_snapshot(
        service=service,
        activity_type=activity_type,
        anchor_type=anchor_type,
        anchor_id=int(anchor_id),
        suggestion_type="study_suggestions",
        payload_json=payload,
        refreshed_from_snapshot_id=refreshed_from_snapshot_id,
    )


__all__ = [
    "get_anchor_status",
    "load_live_evidence_for_snapshot",
    "refresh_snapshot_for_anchor",
    "serialize_snapshot",
]
