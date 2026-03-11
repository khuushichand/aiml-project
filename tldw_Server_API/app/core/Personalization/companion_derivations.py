from __future__ import annotations

from collections import Counter
from typing import Any

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB


def derive_companion_knowledge_cards(
    db: PersonalizationDB,
    *,
    user_id: str,
    limit: int = 500,
) -> list[dict[str, Any]]:
    events, _ = db.list_companion_activity_events(user_id, limit=limit, offset=0)
    if not events:
        return []

    tag_counter: Counter[str] = Counter()
    evidence_by_tag: dict[str, list[dict[str, Any]]] = {}

    for event in events:
        for raw_tag in event.get("tags") or []:
            tag = str(raw_tag or "").strip()
            if not tag:
                continue
            tag_counter[tag] += 1
            evidence_by_tag.setdefault(tag, [])
            if len(evidence_by_tag[tag]) >= 5:
                continue
            evidence_by_tag[tag].append(
                {
                    "event_id": event["id"],
                    "event_type": event["event_type"],
                    "source_type": event["source_type"],
                    "source_id": event["source_id"],
                    "created_at": event["created_at"],
                }
            )

    if not tag_counter:
        return []

    top_tag, top_count = max(tag_counter.items(), key=lambda item: (item[1], item[0]))
    if top_count < 2:
        return []

    evidence = evidence_by_tag.get(top_tag, [])
    score = min(1.0, top_count / max(1, len(events)))
    return [
        {
            "card_type": "project_focus",
            "title": "Current focus",
            "summary": f"Recent explicit activity clusters around '{top_tag}'.",
            "evidence": evidence,
            "score": score,
            "status": "active",
        }
    ]
