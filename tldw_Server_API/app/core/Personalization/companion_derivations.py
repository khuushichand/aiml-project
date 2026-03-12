from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB


_MAX_EVIDENCE = 5
_STALE_FOLLOWUP_DAYS = 7


def _coerce_now(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _parse_created_at(raw: Any, *, default: datetime) -> datetime:
    text = str(raw or "").strip()
    if not text:
        return default
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return default
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().replace("_", " ").split())


def _event_evidence(event: dict[str, Any]) -> dict[str, Any]:
    metadata = event.get("metadata") or {}
    return {
        "event_id": event["id"],
        "event_type": event["event_type"],
        "source_type": event["source_type"],
        "source_id": event["source_id"],
        "title": _normalize_text(metadata.get("title")),
        "created_at": event["created_at"],
    }


def _goal_evidence(goal: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal_id": goal["id"],
        "title": goal["title"],
        "status": goal["status"],
        "progress_mode": goal.get("progress_mode"),
        "updated_at": goal.get("updated_at"),
        "signal_count": max(1, len(goal.get("evidence") or [])),
    }


def _append_evidence(bucket: dict[str, list[dict[str, Any]]], key: str, item: dict[str, Any]) -> None:
    bucket.setdefault(key, [])
    if len(bucket[key]) >= _MAX_EVIDENCE:
        return
    bucket[key].append(item)


def _score_signal(signal_count: int, total_events: int) -> float:
    if total_events <= 0:
        return 0.0
    return min(1.0, float(signal_count) / float(total_events))


def derive_companion_knowledge_cards(
    db: PersonalizationDB,
    *,
    user_id: str,
    limit: int = 500,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    events, _ = db.list_companion_activity_events(user_id, limit=limit, offset=0)
    all_goals = db.list_companion_goals(user_id)
    active_goals = [goal for goal in all_goals if str(goal.get("status") or "").lower() == "active"]
    if not events and not active_goals:
        return []

    current_time = _coerce_now(now)
    stale_cutoff = current_time - timedelta(days=_STALE_FOLLOWUP_DAYS)

    tag_counter: Counter[str] = Counter()
    tag_evidence: dict[str, list[dict[str, Any]]] = {}
    tag_latest: dict[str, datetime] = {}

    source_counter: Counter[str] = Counter()
    source_evidence: dict[str, list[dict[str, Any]]] = {}

    for event in events:
        event_time = _parse_created_at(event.get("created_at"), default=current_time)
        evidence = _event_evidence(event)

        source_key = _normalize_text(event.get("source_type") or event.get("surface"))
        if source_key:
            source_counter[source_key] += 1
            _append_evidence(source_evidence, source_key, evidence)

        for raw_tag in event.get("tags") or []:
            tag = _normalize_text(raw_tag)
            if not tag:
                continue
            tag_counter[tag] += 1
            _append_evidence(tag_evidence, tag, evidence)
            latest_seen = tag_latest.get(tag)
            if latest_seen is None or event_time > latest_seen:
                tag_latest[tag] = event_time

    cards: list[dict[str, Any]] = []
    repeated_tags = sorted(
        ((tag, count) for tag, count in tag_counter.items() if count >= 2),
        key=lambda item: (-item[1], item[0]),
    )
    total_events = len(events)

    if repeated_tags:
        top_tag, top_count = repeated_tags[0]
        cards.append(
            {
                "card_type": "project_focus",
                "title": "Current focus",
                "summary": f"Recent explicit activity clusters around '{top_tag}'.",
                "evidence": tag_evidence.get(top_tag, []),
                "score": _score_signal(top_count, total_events),
                "status": "active",
            }
        )

        if len(repeated_tags) > 1:
            topic_tag, topic_count = repeated_tags[1]
            cards.append(
                {
                    "card_type": "topic_focus",
                    "title": "Emerging topic",
                    "summary": f"A second stream of explicit activity keeps returning to '{topic_tag}'.",
                    "evidence": tag_evidence.get(topic_tag, []),
                    "score": _score_signal(topic_count, total_events),
                    "status": "active",
                }
            )

        stale_candidates = [
            (tag, count, tag_latest.get(tag))
            for tag, count in repeated_tags
            if tag_latest.get(tag) is not None and tag_latest[tag] <= stale_cutoff
        ]
        if stale_candidates:
            stale_tag, stale_count, stale_at = sorted(
                stale_candidates,
                key=lambda item: (-item[1], item[2], item[0]),
            )[0]
            stale_label = stale_at.date().isoformat() if stale_at is not None else "an earlier date"
            cards.append(
                {
                    "card_type": "stale_followup",
                    "title": "Stale follow-up",
                    "summary": f"No fresh explicit activity has touched '{stale_tag}' since {stale_label}.",
                    "evidence": tag_evidence.get(stale_tag, []),
                    "score": _score_signal(stale_count, total_events),
                    "status": "active",
                }
            )

    repeated_sources = sorted(
        ((source, count) for source, count in source_counter.items() if count >= 2),
        key=lambda item: (-item[1], item[0]),
    )
    if repeated_sources:
        top_source, source_count = repeated_sources[0]
        cards.append(
            {
                "card_type": "source_focus",
                "title": "Primary source flow",
                "summary": f"Most explicit captures are currently arriving through {top_source}.",
                "evidence": source_evidence.get(top_source, []),
                "score": _score_signal(source_count, total_events),
                "status": "active",
            }
        )

    if active_goals:
        sorted_goals = sorted(
            active_goals,
            key=lambda goal: (
                goal.get("updated_at") or "",
                goal.get("title") or "",
            ),
            reverse=True,
        )
        lead_goal = sorted_goals[0]
        cards.append(
            {
                "card_type": "active_goal_signal",
                "title": "Active goal",
                "summary": f"Active companion work is anchored by '{lead_goal['title']}'.",
                "evidence": [_goal_evidence(goal) for goal in sorted_goals[:_MAX_EVIDENCE]],
                "score": min(1.0, 0.4 + (0.2 * min(len(sorted_goals), 3))),
                "status": "active",
            }
        )

    return sorted(cards, key=lambda card: (-float(card["score"]), str(card["card_type"])))
