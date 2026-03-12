from __future__ import annotations

"""Deterministic lexical ranking for bounded companion context candidates."""

import re
from typing import Any, Callable


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MAX_CARD_CANDIDATES = 12
_MAX_GOAL_CANDIDATES = 12
_MAX_ACTIVITY_CANDIDATES = 18


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _tokenize(value: Any) -> set[str]:
    text = _normalize_text(value)
    return {token for token in _TOKEN_RE.findall(text) if len(token) >= 2}


def _flatten_values(value: Any, *, limit: int = 12) -> list[str]:
    pending = [value]
    flattened: list[str] = []
    while pending and len(flattened) < limit:
        current = pending.pop(0)
        if current in (None, "", [], {}):
            continue
        if isinstance(current, dict):
            pending.extend(list(current.values())[:limit])
            continue
        if isinstance(current, (list, tuple, set)):
            pending.extend(list(current)[:limit])
            continue
        flattened.append(str(current))
    return flattened


def _card_text(card: dict[str, Any]) -> str:
    fragments = [
        card.get("title"),
        card.get("summary"),
        card.get("card_type"),
        *_flatten_values(card.get("evidence"), limit=8),
    ]
    return " ".join(fragment for fragment in fragments if fragment)


def _goal_text(goal: dict[str, Any]) -> str:
    fragments = [
        goal.get("title"),
        goal.get("description"),
        goal.get("goal_type"),
        *_flatten_values(goal.get("config"), limit=6),
        *_flatten_values(goal.get("progress"), limit=6),
    ]
    return " ".join(fragment for fragment in fragments if fragment)


def _activity_text(event: dict[str, Any]) -> str:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    fragments = [
        event.get("event_type"),
        event.get("source_type"),
        *(event.get("tags") or []),
        metadata.get("title"),
        metadata.get("name"),
        metadata.get("page_title"),
        metadata.get("summary"),
        metadata.get("selection"),
        *_flatten_values(metadata, limit=8),
    ]
    return " ".join(fragment for fragment in fragments if fragment)


def _score_candidate(query_tokens: set[str], candidate_text: str) -> float:
    if not query_tokens:
        return 0.0
    normalized_text = _normalize_text(candidate_text)
    candidate_tokens = _tokenize(normalized_text)
    overlap = query_tokens & candidate_tokens
    if not overlap:
        return 0.0
    phrase_bonus = 0.0
    if len(overlap) >= 2:
        joined_overlap = " ".join(sorted(overlap))
        if joined_overlap and joined_overlap in normalized_text:
            phrase_bonus = 0.5
    density_bonus = len(overlap) / max(len(candidate_tokens), 1)
    return float(len(overlap)) + phrase_bonus + density_bonus


def _rank_items(
    items: list[dict[str, Any]],
    *,
    query_tokens: set[str],
    text_builder: Callable[[dict[str, Any]], str],
    max_items: int,
) -> list[dict[str, Any]]:
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, item in enumerate(items):
        score = _score_candidate(query_tokens, text_builder(item))
        if score <= 0:
            continue
        scored.append((score, idx, item))
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [item for _score, _idx, item in scored[:max_items]]


def rank_companion_candidates(
    *,
    query: str | None,
    cards: list[dict[str, Any]],
    goals: list[dict[str, Any]],
    activity_rows: list[dict[str, Any]],
    max_cards: int = 3,
    max_goals: int = 2,
    max_activities: int = 3,
) -> dict[str, Any]:
    """Rank bounded companion candidates against the live query using lexical overlap."""
    safe_max_cards = max(0, int(max_cards))
    safe_max_goals = max(0, int(max_goals))
    safe_max_activities = max(0, int(max_activities))
    bounded_cards = list(cards[:_MAX_CARD_CANDIDATES])
    bounded_goals = list(goals[:_MAX_GOAL_CANDIDATES])
    bounded_activities = list(activity_rows[:_MAX_ACTIVITY_CANDIDATES])
    query_tokens = _tokenize(query)

    if not query_tokens:
        selected_cards = bounded_cards[:safe_max_cards]
        selected_goals = bounded_goals[:safe_max_goals]
        selected_activities = bounded_activities[:safe_max_activities]
        return {
            "mode": "recent_fallback",
            "cards": selected_cards,
            "goals": selected_goals,
            "activity_rows": selected_activities,
            "card_ids": [str(card.get("id")) for card in selected_cards if card.get("id")],
            "goal_ids": [str(goal.get("id")) for goal in selected_goals if goal.get("id")],
            "activity_ids": [str(row.get("id")) for row in selected_activities if row.get("id")],
        }

    selected_cards = _rank_items(
        bounded_cards,
        query_tokens=query_tokens,
        text_builder=_card_text,
        max_items=safe_max_cards,
    )
    selected_goals = _rank_items(
        bounded_goals,
        query_tokens=query_tokens,
        text_builder=_goal_text,
        max_items=safe_max_goals,
    )
    selected_activities = _rank_items(
        bounded_activities,
        query_tokens=query_tokens,
        text_builder=_activity_text,
        max_items=safe_max_activities,
    )

    if not (selected_cards or selected_goals or selected_activities):
        selected_cards = bounded_cards[:safe_max_cards]
        selected_goals = bounded_goals[:safe_max_goals]
        selected_activities = bounded_activities[:safe_max_activities]
        mode = "recent_fallback"
    else:
        mode = "ranked"

    return {
        "mode": mode,
        "cards": selected_cards,
        "goals": selected_goals,
        "activity_rows": selected_activities,
        "card_ids": [str(card.get("id")) for card in selected_cards if card.get("id")],
        "goal_ids": [str(goal.get("id")) for goal in selected_goals if goal.get("id")],
        "activity_ids": [str(row.get("id")) for row in selected_activities if row.get("id")],
    }


__all__ = [
    "rank_companion_candidates",
]
