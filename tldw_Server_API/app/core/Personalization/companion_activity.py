from __future__ import annotations

import hashlib
import json
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


def _payload_fingerprint(payload: dict[str, Any] | None) -> str:
    try:
        serialized = json.dumps(payload or {}, sort_keys=True, ensure_ascii=True, default=str)
    except Exception:
        serialized = json.dumps({"unserializable": True}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(serialized.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


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


def record_reading_note_linked(
    *,
    user_id: str | int | None,
    item_id: int,
    note_id: str,
    item_title: str | None = None,
    link_created_at: str | None = None,
) -> str | None:
    source_id = f"{item_id}:{note_id}"
    return record_companion_activity(
        user_id=user_id,
        event_type="reading_note_linked",
        source_type="reading_note_link",
        source_id=source_id,
        surface="api.reading",
        dedupe_key=f"reading.note.link:{source_id}:{link_created_at or 'na'}",
        provenance=_explicit_provenance(
            route=f"/api/v1/reading/items/{item_id}/links/note",
            action="link_note",
            source_timestamp=link_created_at,
        ),
        metadata={
            "item_id": item_id,
            "note_id": str(note_id),
            "title": item_title,
            "item_title": item_title,
        },
    )


def record_reading_note_unlinked(
    *,
    user_id: str | int | None,
    item_id: int,
    note_id: str,
    item_title: str | None = None,
    link_created_at: str | None = None,
) -> str | None:
    source_id = f"{item_id}:{note_id}"
    return record_companion_activity(
        user_id=user_id,
        event_type="reading_note_unlinked",
        source_type="reading_note_link",
        source_id=source_id,
        surface="api.reading",
        dedupe_key=f"reading.note.unlink:{source_id}:{link_created_at or 'na'}",
        provenance=_explicit_provenance(
            route=f"/api/v1/reading/items/{item_id}/links/note/{note_id}",
            action="unlink_note",
            source_timestamp=link_created_at,
        ),
        metadata={
            "item_id": item_id,
            "note_id": str(note_id),
            "title": item_title,
            "item_title": item_title,
        },
    )


def _reading_highlight_metadata(highlight: Any, *, item_title: str | None = None) -> dict[str, Any]:
    return {
        "item_id": getattr(highlight, "item_id", None),
        "title": item_title,
        "item_title": item_title,
        "quote": getattr(highlight, "quote", None),
        "note": getattr(highlight, "note", None),
        "color": getattr(highlight, "color", None),
        "state": getattr(highlight, "state", None),
        "anchor_strategy": getattr(highlight, "anchor_strategy", None),
        "start_offset": getattr(highlight, "start_offset", None),
        "end_offset": getattr(highlight, "end_offset", None),
    }


def record_reading_highlight_created(
    *,
    user_id: str | int | None,
    highlight: Any,
    item_title: str | None = None,
) -> str | None:
    highlight_id = str(getattr(highlight, "id"))
    item_id = int(getattr(highlight, "item_id"))
    created_at = getattr(highlight, "created_at", None)
    return record_companion_activity(
        user_id=user_id,
        event_type="reading_highlight_created",
        source_type="reading_highlight",
        source_id=highlight_id,
        surface="api.reading",
        dedupe_key=f"reading.highlight.create:{highlight_id}:{created_at or 'na'}",
        provenance=_explicit_provenance(
            route=f"/api/v1/reading/items/{item_id}/highlight",
            action="create_highlight",
            source_timestamp=created_at,
        ),
        metadata=_reading_highlight_metadata(highlight, item_title=item_title),
    )


def record_reading_highlight_updated(
    *,
    user_id: str | int | None,
    highlight: Any,
    item_title: str | None = None,
    patch: dict[str, Any] | None = None,
) -> str | None:
    highlight_id = str(getattr(highlight, "id"))
    fingerprint = _payload_fingerprint(patch)
    return record_companion_activity(
        user_id=user_id,
        event_type="reading_highlight_updated",
        source_type="reading_highlight",
        source_id=highlight_id,
        surface="api.reading",
        dedupe_key=f"reading.highlight.update:{highlight_id}:{fingerprint}",
        provenance=_explicit_provenance(
            route=f"/api/v1/reading/highlights/{highlight_id}",
            action="update_highlight",
            source_timestamp=getattr(highlight, "created_at", None),
        ),
        metadata={
            **_reading_highlight_metadata(highlight, item_title=item_title),
            "patch": dict(patch or {}),
        },
    )


def record_reading_highlight_deleted(
    *,
    user_id: str | int | None,
    highlight: Any,
    item_title: str | None = None,
) -> str | None:
    highlight_id = str(getattr(highlight, "id"))
    return record_companion_activity(
        user_id=user_id,
        event_type="reading_highlight_deleted",
        source_type="reading_highlight",
        source_id=highlight_id,
        surface="api.reading",
        dedupe_key=f"reading.highlight.delete:{highlight_id}",
        provenance=_explicit_provenance(
            route=f"/api/v1/reading/highlights/{highlight_id}",
            action="delete_highlight",
            source_timestamp=getattr(highlight, "created_at", None),
        ),
        metadata=_reading_highlight_metadata(highlight, item_title=item_title),
    )


def _value(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _content_preview(value: Any, *, max_chars: int = 240) -> str | None:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return None
    safe_limit = max(8, int(max_chars))
    if len(text) <= safe_limit:
        return text
    suffix = "... [truncated]"
    if safe_limit <= len(suffix):
        return text[:safe_limit]
    return f"{text[: safe_limit - len(suffix)]}{suffix}"


def _note_tags(note: Any) -> list[str] | None:
    keywords = _value(note, "keywords")
    if not isinstance(keywords, list):
        return None
    tags: list[str] = []
    for keyword in keywords:
        if isinstance(keyword, dict):
            raw_value = keyword.get("keyword")
        else:
            raw_value = getattr(keyword, "keyword", None)
        normalized = str(raw_value or "").strip()
        if normalized and normalized not in tags:
            tags.append(normalized)
    return tags or None


def _note_metadata(note: Any) -> dict[str, Any]:
    return {
        "title": _value(note, "title"),
        "content_preview": _content_preview(_value(note, "content")),
        "version": _value(note, "version"),
        "conversation_id": _value(note, "conversation_id"),
        "message_id": _value(note, "message_id"),
    }


def _note_timestamp(note: Any, *, prefer_created: bool = False) -> str | None:
    if prefer_created:
        return _value(note, "created_at") or _value(note, "last_modified") or _value(note, "updated_at")
    return _value(note, "last_modified") or _value(note, "updated_at") or _value(note, "created_at")


def record_note_created(*, user_id: str | int | None, note: Any) -> str | None:
    note_id = str(_value(note, "id"))
    source_timestamp = _note_timestamp(note, prefer_created=True)
    return record_companion_activity(
        user_id=user_id,
        event_type="note_created",
        source_type="note",
        source_id=note_id,
        surface="api.notes",
        dedupe_key=f"notes.create:{note_id}",
        tags=_note_tags(note),
        provenance=_explicit_provenance(
            route="/api/v1/notes/",
            action="create",
            source_timestamp=source_timestamp,
        ),
        metadata=_note_metadata(note),
    )


def record_note_updated(
    *,
    user_id: str | int | None,
    note: Any,
    route: str,
    action: str,
    patch: dict[str, Any] | None = None,
) -> str | None:
    note_id = str(_value(note, "id"))
    source_timestamp = _note_timestamp(note)
    version = _value(note, "version")
    fingerprint = _payload_fingerprint(patch)
    changed_fields = sorted(str(key) for key in dict(patch or {}).keys())
    return record_companion_activity(
        user_id=user_id,
        event_type="note_updated",
        source_type="note",
        source_id=note_id,
        surface="api.notes",
        dedupe_key=f"notes.update:{note_id}:{version or source_timestamp or 'na'}:{fingerprint}",
        tags=_note_tags(note),
        provenance=_explicit_provenance(
            route=route,
            action=action,
            source_timestamp=source_timestamp,
        ),
        metadata={
            **_note_metadata(note),
            "changed_fields": changed_fields,
        },
    )


def record_note_deleted(
    *,
    user_id: str | int | None,
    note: Any,
    deleted_version: int | None = None,
) -> str | None:
    note_id = str(_value(note, "id"))
    source_timestamp = _note_timestamp(note)
    effective_version = deleted_version if deleted_version is not None else _value(note, "version")
    return record_companion_activity(
        user_id=user_id,
        event_type="note_deleted",
        source_type="note",
        source_id=note_id,
        surface="api.notes",
        dedupe_key=f"notes.delete:{note_id}:{effective_version or source_timestamp or 'na'}",
        tags=_note_tags(note),
        provenance=_explicit_provenance(
            route=f"/api/v1/notes/{note_id}",
            action="delete",
            source_timestamp=source_timestamp,
        ),
        metadata={
            **_note_metadata(note),
            "version": effective_version,
            "deleted": True,
            "hard_delete": False,
        },
    )


def record_note_restored(*, user_id: str | int | None, note: Any) -> str | None:
    note_id = str(_value(note, "id"))
    source_timestamp = _note_timestamp(note)
    version = _value(note, "version")
    return record_companion_activity(
        user_id=user_id,
        event_type="note_restored",
        source_type="note",
        source_id=note_id,
        surface="api.notes",
        dedupe_key=f"notes.restore:{note_id}:{version or source_timestamp or 'na'}",
        tags=_note_tags(note),
        provenance=_explicit_provenance(
            route=f"/api/v1/notes/{note_id}/restore",
            action="restore",
            source_timestamp=source_timestamp,
        ),
        metadata={
            **_note_metadata(note),
            "deleted": False,
            "hard_delete": False,
        },
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


def _watchlist_source_metadata(source: Any) -> dict[str, Any]:
    settings = _value(source, "settings")
    if settings is None:
        raw_settings_json = _value(source, "settings_json")
        if isinstance(raw_settings_json, str) and raw_settings_json.strip():
            try:
                settings = json.loads(raw_settings_json)
            except Exception:
                settings = None
    settings_keys = sorted(str(key) for key in settings.keys()) if isinstance(settings, dict) else []
    return {
        "name": _value(source, "name"),
        "url": _value(source, "url"),
        "source_type": _value(source, "source_type"),
        "active": _value(source, "active"),
        "status": _value(source, "status"),
        "group_ids": list(_value(source, "group_ids") or []),
        "settings_keys": settings_keys,
    }


def _watchlist_source_timestamp(source: Any) -> str | None:
    return _value(source, "updated_at") or _value(source, "created_at")


def record_watchlist_source_created(*, user_id: str | int | None, source: Any) -> str | None:
    source_id = str(_value(source, "id"))
    source_timestamp = _watchlist_source_timestamp(source)
    return record_companion_activity(
        user_id=user_id,
        event_type="watchlist_source_created",
        source_type="watchlist_source",
        source_id=source_id,
        surface="api.watchlists",
        dedupe_key=f"watchlists.source.create:{source_id}",
        tags=list(getattr(source, "tags", None) or []),
        provenance=_explicit_provenance(
            route="/api/v1/watchlists/sources",
            action="create",
            source_timestamp=source_timestamp,
        ),
        metadata=_watchlist_source_metadata(source),
    )


def record_watchlist_source_updated(
    *,
    user_id: str | int | None,
    source: Any,
    patch: dict[str, Any] | None = None,
    event_timestamp: str | None = None,
) -> str | None:
    source_id = str(_value(source, "id"))
    source_timestamp = event_timestamp or _watchlist_source_timestamp(source)
    fingerprint = _payload_fingerprint(patch)
    changed_fields = sorted(str(key) for key in dict(patch or {}).keys())
    return record_companion_activity(
        user_id=user_id,
        event_type="watchlist_source_updated",
        source_type="watchlist_source",
        source_id=source_id,
        surface="api.watchlists",
        dedupe_key=f"watchlists.source.update:{source_id}:{source_timestamp or 'na'}:{fingerprint}",
        tags=list(_value(source, "tags") or []),
        provenance=_explicit_provenance(
            route=f"/api/v1/watchlists/sources/{source_id}",
            action="update",
            source_timestamp=source_timestamp,
        ),
        metadata={
            **_watchlist_source_metadata(source),
            "changed_fields": changed_fields,
        },
    )


def record_watchlist_source_deleted(
    *,
    user_id: str | int | None,
    source: Any,
    event_timestamp: str | None = None,
    restore_window_seconds: int | None = None,
) -> str | None:
    source_id = str(_value(source, "id"))
    source_timestamp = event_timestamp or _watchlist_source_timestamp(source)
    return record_companion_activity(
        user_id=user_id,
        event_type="watchlist_source_deleted",
        source_type="watchlist_source",
        source_id=source_id,
        surface="api.watchlists",
        dedupe_key=f"watchlists.source.delete:{source_id}:{source_timestamp or 'na'}",
        tags=list(_value(source, "tags") or []),
        provenance=_explicit_provenance(
            route=f"/api/v1/watchlists/sources/{source_id}",
            action="delete",
            source_timestamp=source_timestamp,
        ),
        metadata={
            **_watchlist_source_metadata(source),
            "deleted": True,
            "hard_delete": False,
            "restore_window_seconds": restore_window_seconds,
        },
    )


def record_watchlist_source_restored(
    *,
    user_id: str | int | None,
    source: Any,
    event_timestamp: str | None = None,
) -> str | None:
    source_id = str(_value(source, "id"))
    source_timestamp = event_timestamp or _watchlist_source_timestamp(source)
    return record_companion_activity(
        user_id=user_id,
        event_type="watchlist_source_restored",
        source_type="watchlist_source",
        source_id=source_id,
        surface="api.watchlists",
        dedupe_key=f"watchlists.source.restore:{source_id}:{source_timestamp or 'na'}",
        tags=list(_value(source, "tags") or []),
        provenance=_explicit_provenance(
            route=f"/api/v1/watchlists/sources/{source_id}/restore",
            action="restore",
            source_timestamp=source_timestamp,
        ),
        metadata={
            **_watchlist_source_metadata(source),
            "deleted": False,
            "hard_delete": False,
        },
    )


def _reminder_task_metadata(task: Any) -> dict[str, Any]:
    return {
        "title": _value(task, "title"),
        "body_preview": _content_preview(_value(task, "body"), max_chars=160),
        "schedule_kind": _value(task, "schedule_kind"),
        "enabled": _value(task, "enabled"),
        "link_type": _value(task, "link_type"),
        "link_id": _value(task, "link_id"),
        "link_url": _value(task, "link_url"),
    }


def _reminder_task_timestamp(task: Any) -> str | None:
    return _value(task, "updated_at") or _value(task, "created_at")


def record_reminder_task_created(*, user_id: str | int | None, task: Any) -> str | None:
    task_id = str(_value(task, "id"))
    source_timestamp = _reminder_task_timestamp(task)
    return record_companion_activity(
        user_id=user_id,
        event_type="reminder_task_created",
        source_type="reminder_task",
        source_id=task_id,
        surface="api.tasks",
        dedupe_key=f"reminder.task.create:{task_id}",
        provenance=_explicit_provenance(
            route="/api/v1/tasks",
            action="create",
            source_timestamp=source_timestamp,
        ),
        metadata=_reminder_task_metadata(task),
    )


def record_reminder_task_updated(
    *,
    user_id: str | int | None,
    task: Any,
    patch: dict[str, Any] | None = None,
) -> str | None:
    task_id = str(_value(task, "id"))
    source_timestamp = _reminder_task_timestamp(task)
    fingerprint = _payload_fingerprint(patch)
    changed_fields = sorted(str(key) for key in dict(patch or {}).keys())
    return record_companion_activity(
        user_id=user_id,
        event_type="reminder_task_updated",
        source_type="reminder_task",
        source_id=task_id,
        surface="api.tasks",
        dedupe_key=f"reminder.task.update:{task_id}:{source_timestamp or 'na'}:{fingerprint}",
        provenance=_explicit_provenance(
            route=f"/api/v1/tasks/{task_id}",
            action="update",
            source_timestamp=source_timestamp,
        ),
        metadata={
            **_reminder_task_metadata(task),
            "changed_fields": changed_fields,
        },
    )


def record_reminder_task_deleted(*, user_id: str | int | None, task: Any) -> str | None:
    task_id = str(_value(task, "id"))
    source_timestamp = _reminder_task_timestamp(task)
    return record_companion_activity(
        user_id=user_id,
        event_type="reminder_task_deleted",
        source_type="reminder_task",
        source_id=task_id,
        surface="api.tasks",
        dedupe_key=f"reminder.task.delete:{task_id}:{source_timestamp or 'na'}",
        provenance=_explicit_provenance(
            route=f"/api/v1/tasks/{task_id}",
            action="delete",
            source_timestamp=source_timestamp,
        ),
        metadata={
            **_reminder_task_metadata(task),
            "hard_delete": True,
        },
    )
