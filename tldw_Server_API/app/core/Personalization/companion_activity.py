from __future__ import annotations

import sqlite3
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.feature_flags import is_personalization_enabled


def _open_db_for_user(user_id: str | int) -> tuple[PersonalizationDB, str]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("user_id is required")
    db_path = DatabasePaths.get_personalization_db_path(user_id)
    return PersonalizationDB(str(db_path)), normalized_user_id


def _profile_opted_in(db: PersonalizationDB, user_id: str) -> bool:
    profile = db.get_or_create_profile(user_id)
    return bool(profile.get("enabled", 0))


def _unique_conflict(exc: sqlite3.IntegrityError) -> bool:
    return "unique constraint failed" in str(exc).strip().lower()


def _explicit_provenance(
    *,
    route: str,
    action: str,
    source_timestamp: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "capture_mode": "explicit",
        "route": route,
        "action": action,
    }
    if source_timestamp:
        payload["source_timestamp"] = source_timestamp
    return payload


def record_companion_activity(
    *,
    user_id: str | int | None,
    event_type: str,
    source_type: str,
    source_id: str | int,
    surface: str,
    dedupe_key: str,
    tags: list[str] | None = None,
    provenance: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    if user_id is None or not is_personalization_enabled():
        return None

    try:
        db, normalized_user_id = _open_db_for_user(user_id)
        if not _profile_opted_in(db, normalized_user_id):
            return None
        safe_provenance = dict(provenance or {})
        safe_provenance.setdefault("capture_mode", "explicit")
        return db.insert_companion_activity_event(
            user_id=normalized_user_id,
            event_type=event_type,
            source_type=source_type,
            source_id=str(source_id),
            surface=surface,
            dedupe_key=dedupe_key,
            tags=tags,
            provenance=safe_provenance,
            metadata=metadata,
        )
    except sqlite3.IntegrityError as exc:
        if _unique_conflict(exc):
            logger.debug("companion activity duplicate skipped: {}", dedupe_key)
            return None
        logger.debug("companion activity insert skipped: {}", exc)
        return None
    except Exception as exc:
        logger.debug("companion activity capture skipped: {}", exc)
        return None


def record_reading_item_saved(*, user_id: str | int | None, item: Any) -> str | None:
    item_id = str(getattr(item, "id"))
    source_timestamp = getattr(item, "updated_at", None) or getattr(item, "created_at", None)
    return record_companion_activity(
        user_id=user_id,
        event_type="reading_item_saved",
        source_type="reading_item",
        source_id=item_id,
        surface="api.reading",
        dedupe_key=f"reading.save:{item_id}",
        tags=list(getattr(item, "tags", None) or []),
        provenance=_explicit_provenance(
            route="/api/v1/reading/save",
            action="save",
            source_timestamp=source_timestamp,
        ),
        metadata={
            "title": getattr(item, "title", None),
            "url": getattr(item, "url", None),
            "canonical_url": getattr(item, "canonical_url", None),
            "status": getattr(item, "status", None),
            "favorite": bool(getattr(item, "favorite", False)),
        },
    )


def record_reading_item_updated(*, user_id: str | int | None, item: Any) -> str | None:
    item_id = str(getattr(item, "id"))
    source_timestamp = getattr(item, "updated_at", None) or getattr(item, "created_at", None)
    return record_companion_activity(
        user_id=user_id,
        event_type="reading_item_updated",
        source_type="reading_item",
        source_id=item_id,
        surface="api.reading",
        dedupe_key=f"reading.update:{item_id}:{source_timestamp or 'na'}",
        tags=list(getattr(item, "tags", None) or []),
        provenance=_explicit_provenance(
            route=f"/api/v1/reading/items/{item_id}",
            action="update",
            source_timestamp=source_timestamp,
        ),
        metadata={
            "title": getattr(item, "title", None),
            "status": getattr(item, "status", None),
            "favorite": bool(getattr(item, "favorite", False)),
            "notes": getattr(item, "notes", None),
        },
    )


def record_reading_item_archived(*, user_id: str | int | None, item: Any) -> str | None:
    item_id = str(getattr(item, "id"))
    source_timestamp = getattr(item, "updated_at", None) or getattr(item, "created_at", None)
    return record_companion_activity(
        user_id=user_id,
        event_type="reading_item_archived",
        source_type="reading_item",
        source_id=item_id,
        surface="api.reading",
        dedupe_key=f"reading.archive:{item_id}:{source_timestamp or 'na'}",
        tags=list(getattr(item, "tags", None) or []),
        provenance=_explicit_provenance(
            route=f"/api/v1/reading/items/{item_id}",
            action="archive",
            source_timestamp=source_timestamp,
        ),
        metadata={
            "title": getattr(item, "title", None),
            "status": getattr(item, "status", None),
            "hard_delete": False,
        },
    )


def record_reading_item_deleted(*, user_id: str | int | None, item_id: int) -> str | None:
    return record_companion_activity(
        user_id=user_id,
        event_type="reading_item_deleted",
        source_type="reading_item",
        source_id=str(item_id),
        surface="api.reading",
        dedupe_key=f"reading.delete:{item_id}",
        provenance=_explicit_provenance(
            route=f"/api/v1/reading/items/{item_id}",
            action="delete",
        ),
        metadata={"hard_delete": True},
    )


def record_persona_session_started(
    *,
    user_id: str | int | None,
    session_id: str,
    persona_id: str,
    runtime_mode: str | None,
    scope_snapshot_id: str | None,
) -> str | None:
    return record_companion_activity(
        user_id=user_id,
        event_type="persona_session_started",
        source_type="persona_session",
        source_id=session_id,
        surface="api.persona",
        dedupe_key=f"persona.session.started:{session_id}",
        tags=[persona_id],
        provenance=_explicit_provenance(
            route="/api/v1/persona/session",
            action="start",
        ),
        metadata={
            "persona_id": persona_id,
            "runtime_mode": runtime_mode,
            "scope_snapshot_id": scope_snapshot_id,
        },
    )
