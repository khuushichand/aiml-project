from __future__ import annotations

"""Jobs-backed companion reflection generation and notification helpers."""

import asyncio
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Personalization.companion_lifecycle import rebuild_companion_scope


COMPANION_REFLECTION_DOMAIN = "companion"
COMPANION_REFLECTION_JOB_TYPE = "companion_reflection"
COMPANION_REBUILD_JOB_TYPE = "companion_rebuild"


def companion_reflection_queue() -> str:
    """Return the queue name used for companion reflection jobs."""
    queue = "default"
    return queue


def _parse_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _resolve_user_id(job: dict[str, Any], payload: dict[str, Any]) -> int:
    owner = job.get("owner_user_id") or payload.get("user_id")
    if owner is None or str(owner).strip() == "":
        return int(DatabasePaths.get_single_user_id())
    return int(owner)


def _coerce_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_hhmm(raw: Any) -> tuple[int, int] | None:
    text = str(raw or "").strip()
    if len(text) != 5 or text[2] != ":":
        return None
    try:
        hour = int(text[:2])
        minute = int(text[3:])
    except (TypeError, ValueError):
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour, minute


def _quiet_hours_active(profile: dict[str, Any], now: datetime) -> bool:
    start = _parse_hhmm(profile.get("quiet_hours_start"))
    end = _parse_hhmm(profile.get("quiet_hours_end"))
    if start is None or end is None:
        return False
    current_minutes = (now.hour * 60) + now.minute
    start_minutes = (start[0] * 60) + start[1]
    end_minutes = (end[0] * 60) + end[1]
    if start_minutes == end_minutes:
        return False
    if start_minutes < end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes


def _reflection_slot_key(cadence: str, when: datetime) -> str:
    if cadence == "weekly":
        iso_year, iso_week, _iso_weekday = when.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return when.date().isoformat()


def _collect_focus_tags(activity_rows: list[dict[str, Any]]) -> list[str]:
    counts: Counter[str] = Counter()
    for row in activity_rows:
        for tag in row.get("tags") or []:
            normalized = str(tag).strip()
            if normalized:
                counts[normalized] += 1
    return [tag for tag, _count in counts.most_common(5)]


def _build_reflection_payload(
    *,
    cadence: str,
    cards: list[dict[str, Any]],
    activity_rows: list[dict[str, Any]],
    now: datetime,
) -> tuple[str, dict[str, Any], dict[str, Any], list[str]]:
    focus_tags = _collect_focus_tags(activity_rows)
    lead_card = cards[0] if cards else None
    title = f"{cadence.capitalize()} reflection"
    if lead_card is not None:
        summary = f"{lead_card['summary']} {len(activity_rows)} recent explicit actions support this reflection."
    elif focus_tags:
        summary = (
            f"Recent explicit activity clusters around '{focus_tags[0]}', with {len(activity_rows)} supporting actions."
        )
    else:
        summary = f"{len(activity_rows)} recent explicit actions were captured."

    evidence: list[dict[str, Any]] = []
    knowledge_card_ids: list[str] = []
    for card in cards[:3]:
        knowledge_card_ids.append(str(card["id"]))
        evidence.append(
            {
                "kind": "knowledge_card",
                "card_id": str(card["id"]),
                "captured_at": card.get("updated_at"),
                "why_selected": "high scoring derived companion knowledge",
                "signal_count": len(card.get("evidence") or []),
            }
        )
    for row in activity_rows[:5]:
        evidence.append(
            {
                "kind": "activity_event",
                "source_event_id": row["id"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "captured_at": row["created_at"],
                "why_selected": "recent explicit activity",
                "signal_count": max(1, len(row.get("tags") or [])),
            }
        )

    provenance = {
        "source_event_ids": [row["id"] for row in activity_rows[:5]],
        "knowledge_card_ids": knowledge_card_ids,
        "generated_at": now.replace(microsecond=0).isoformat(),
        "signal_count": len(activity_rows[:5]) + len(knowledge_card_ids),
    }
    metadata = {
        "title": title,
        "summary": summary,
        "cadence": cadence,
        "evidence": evidence,
        "generated_at": now.replace(microsecond=0).isoformat(),
        "knowledge_card_ids": knowledge_card_ids,
        "activity_count": len(activity_rows),
    }
    return title, metadata, provenance, focus_tags[:3]


def _lookup_existing_reflection_id(
    *,
    db: PersonalizationDB,
    user_id: str,
    dedupe_key: str,
) -> str | None:
    """Resolve the existing reflection id directly from the dedupe key."""
    return db.get_companion_activity_event_id_by_dedupe_key(
        user_id=user_id,
        dedupe_key=dedupe_key,
    )


def run_companion_reflection_job(
    *,
    user_id: str | int,
    cadence: str,
    job_id: str | int | None = None,
    scheduled_for: str | None = None,
    now: datetime | None = None,
    personalization_db: PersonalizationDB | None = None,
    collections_db: CollectionsDatabase | None = None,
) -> dict[str, Any]:
    """Generate one companion reflection for the given cadence slot."""
    normalized_user_id = str(user_id)
    current_time = _coerce_now(_parse_iso_datetime(scheduled_for) or now)
    db = personalization_db or PersonalizationDB(str(DatabasePaths.get_personalization_db_path(normalized_user_id)))
    cdb = collections_db or CollectionsDatabase.for_user(user_id=int(normalized_user_id))
    profile = db.get_or_create_profile(normalized_user_id)

    if not bool(profile.get("enabled", 1)):
        return {"status": "skipped", "reason": "disabled"}
    if not bool(profile.get("proactive_enabled", 1)):
        return {"status": "skipped", "reason": "proactive_disabled"}
    if _quiet_hours_active(profile, current_time):
        return {"status": "skipped", "reason": "quiet_hours"}

    activity_rows, _total = db.list_companion_activity_events(normalized_user_id, limit=100, offset=0)
    activity_rows = [row for row in activity_rows if row["source_type"] != "companion_reflection"]
    if not activity_rows:
        return {"status": "skipped", "reason": "no_activity"}

    cards = db.list_companion_knowledge_cards(normalized_user_id, status="active")
    title, metadata, provenance, tags = _build_reflection_payload(
        cadence=cadence,
        cards=cards,
        activity_rows=activity_rows,
        now=current_time,
    )
    slot_key = _reflection_slot_key(cadence, current_time)
    dedupe_key = f"companion.reflection:{cadence}:{slot_key}"

    try:
        reflection_id = db.insert_companion_activity_event(
            user_id=normalized_user_id,
            event_type="companion_reflection_generated",
            source_type="companion_reflection",
            source_id=slot_key,
            surface="jobs.companion",
            dedupe_key=dedupe_key,
            tags=tags,
            provenance=provenance,
            metadata=metadata,
        )
    except sqlite3.IntegrityError:
        reflection_id = _lookup_existing_reflection_id(
            db=db,
            user_id=normalized_user_id,
            dedupe_key=dedupe_key,
        )
        if reflection_id is None:
            raise

    notification = cdb.create_user_notification(
        kind="companion_reflection",
        title=title,
        message=metadata["summary"],
        severity="info",
        source_job_id=None if job_id is None else str(job_id),
        source_domain=COMPANION_REFLECTION_DOMAIN,
        source_job_type=COMPANION_REFLECTION_JOB_TYPE,
        link_type="companion_reflection",
        link_id=reflection_id,
        dedupe_key=f"companion_reflection:{cadence}:{slot_key}",
    )
    return {
        "status": "completed",
        "reflection_id": reflection_id,
        "notification_id": notification.id,
    }


async def handle_companion_reflection_job(job: dict[str, Any]) -> dict[str, Any]:
    payload = _parse_payload(job.get("payload"))
    user_id = _resolve_user_id(job, payload)
    job_type = str(job.get("job_type") or "").strip().lower()
    if job_type == COMPANION_REBUILD_JOB_TYPE:
        scope = str(payload.get("scope") or "knowledge").strip().lower() or "knowledge"
        return await asyncio.to_thread(
            rebuild_companion_scope,
            user_id=user_id,
            scope=scope,
        )
    cadence = str(payload.get("cadence") or "daily").strip().lower() or "daily"
    scheduled_for = payload.get("scheduled_for")
    return await asyncio.to_thread(
        run_companion_reflection_job,
        user_id=user_id,
        cadence=cadence,
        job_id=job.get("id"),
        scheduled_for=scheduled_for,
    )


__all__ = [
    "COMPANION_REFLECTION_DOMAIN",
    "COMPANION_REFLECTION_JOB_TYPE",
    "COMPANION_REBUILD_JOB_TYPE",
    "companion_reflection_queue",
    "handle_companion_reflection_job",
    "run_companion_reflection_job",
]
