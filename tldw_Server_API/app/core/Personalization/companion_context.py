from __future__ import annotations

"""Companion context loading for persona retrieval and conversation planning."""

import hashlib
import sqlite3
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.feature_flags import is_personalization_enabled

_MAX_COMPANION_CONTEXT_TOTAL_CHARS = 1_200
_MAX_COMPANION_CONTEXT_ITEM_CHARS = 240
_MAX_COMPANION_CARD_COUNT = 3
_MAX_COMPANION_ACTIVITY_COUNT = 3


def _redacted_user_id(user_id: Any) -> str:
    digest = hashlib.sha1(str(user_id or "").encode("utf-8"), usedforsecurity=False).hexdigest()
    return digest[:12]


def _normalize_snippet(value: Any, *, max_chars: int = _MAX_COMPANION_CONTEXT_ITEM_CHARS) -> str:
    text = " ".join(str(value or "").strip().split())
    safe_limit = max(1, int(max_chars))
    if len(text) <= safe_limit:
        return text
    suffix = "... [truncated]"
    if safe_limit <= len(suffix):
        return text[:safe_limit]
    return f"{text[: safe_limit - len(suffix)]}{suffix}"


def _humanize_event_type(value: Any) -> str:
    parts = [part for part in str(value or "").strip().split("_") if part]
    return " ".join(parts)


def _is_explicit_activity(event: dict[str, Any]) -> bool:
    if str(event.get("source_type") or "").strip().lower() == "companion_reflection":
        return False
    provenance = event.get("provenance")
    if not isinstance(provenance, dict):
        return False
    return str(provenance.get("capture_mode") or "").strip().lower() == "explicit"


def _format_card_line(card: dict[str, Any]) -> str:
    title = _normalize_snippet(card.get("title"), max_chars=80)
    summary = _normalize_snippet(card.get("summary"), max_chars=150)
    if title and summary:
        return f"- {title}: {summary}"
    if title:
        return f"- {title}"
    if summary:
        return f"- {summary}"
    return ""


def _activity_subject(event: dict[str, Any]) -> str:
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    if str(event.get("event_type") or "").strip().lower() == "persona_session_started":
        persona_id = _normalize_snippet(metadata.get("persona_id"), max_chars=80)
        if persona_id:
            return f"Persona session for {persona_id}"

    for key in ("title", "name", "page_title", "selection", "persona_id"):
        value = _normalize_snippet(metadata.get(key), max_chars=100)
        if value:
            return value

    source_type = _normalize_snippet(event.get("source_type"), max_chars=40)
    source_id = _normalize_snippet(event.get("source_id"), max_chars=40)
    if source_type and source_id:
        return f"{source_type} {source_id}"
    return source_type or source_id


def _format_activity_line(event: dict[str, Any]) -> str:
    subject = _activity_subject(event)
    event_label = _normalize_snippet(_humanize_event_type(event.get("event_type")), max_chars=60)
    if subject and event_label:
        return f"- {subject} ({event_label})"
    if subject:
        return f"- {subject}"
    if event_label:
        return f"- {event_label}"
    return ""


def _append_bounded_line(lines: list[str], candidate: str, *, total_used: int) -> tuple[list[str], int]:
    normalized = _normalize_snippet(candidate, max_chars=_MAX_COMPANION_CONTEXT_ITEM_CHARS)
    if not normalized:
        return lines, total_used
    projected = total_used + len(normalized)
    if projected > _MAX_COMPANION_CONTEXT_TOTAL_CHARS:
        remaining = _MAX_COMPANION_CONTEXT_TOTAL_CHARS - total_used
        if remaining <= 0:
            return lines, total_used
        normalized = _normalize_snippet(normalized, max_chars=remaining)
        if not normalized:
            return lines, total_used
        projected = total_used + len(normalized)
    return [*lines, normalized], projected


def load_companion_context(
    *,
    user_id: str | int | None,
    max_cards: int = _MAX_COMPANION_CARD_COUNT,
    max_activities: int = _MAX_COMPANION_ACTIVITY_COUNT,
) -> dict[str, Any]:
    """Load a compact companion context payload for a user."""
    empty_payload = {
        "knowledge_lines": [],
        "activity_lines": [],
        "card_count": 0,
        "activity_count": 0,
    }
    if user_id is None or not is_personalization_enabled():
        return empty_payload

    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return empty_payload

    safe_max_cards = max(0, int(max_cards))
    safe_max_activities = max(0, int(max_activities))

    try:
        db_path = DatabasePaths.get_personalization_db_path(normalized_user_id)
        db = PersonalizationDB(str(db_path))
        profile = db.get_or_create_profile(normalized_user_id)
        if not bool(profile.get("enabled", 0)):
            return empty_payload

        knowledge_lines: list[str] = []
        activity_lines: list[str] = []
        total_used = 0

        cards = db.list_companion_knowledge_cards(normalized_user_id, status="active")
        for card in cards:
            if len(knowledge_lines) >= safe_max_cards:
                break
            line = _format_card_line(card)
            knowledge_lines, total_used = _append_bounded_line(
                knowledge_lines,
                line,
                total_used=total_used,
            )

        activity_rows, _ = db.list_companion_activity_events(
            normalized_user_id,
            limit=max(20, safe_max_activities * 4),
            offset=0,
        )
        for event in activity_rows:
            if len(activity_lines) >= safe_max_activities:
                break
            if not _is_explicit_activity(event):
                continue
            line = _format_activity_line(event)
            activity_lines, total_used = _append_bounded_line(
                activity_lines,
                line,
                total_used=total_used,
            )

        return {
            "knowledge_lines": knowledge_lines,
            "activity_lines": activity_lines,
            "card_count": len(knowledge_lines),
            "activity_count": len(activity_lines),
        }
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        logger.warning(
            "companion context lookup failed for user_hash {}: {}",
            _redacted_user_id(normalized_user_id),
            exc,
        )
        return empty_payload
