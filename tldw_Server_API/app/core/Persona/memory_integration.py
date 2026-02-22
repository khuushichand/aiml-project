"""
Persona memory integration helpers.

This module wires persona session activity to the per-user personalization DB
when personalization is enabled and the user has opted in.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
)
from tldw_Server_API.app.core.DB_Management.Personalization_DB import (
    PersonalizationDB,
    SemanticMemory,
    UsageEvent,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.feature_flags import is_personalization_enabled

_DEFAULT_PERSONA_MEMORY_READ_MODE = "legacy_only"
_DEFAULT_PERSONA_MEMORY_WRITE_MODE = "legacy_only"
_ALLOWED_PERSONA_MEMORY_READ_MODES = {
    "legacy_only",
    "chacha_only",
    "chacha_first_fallback_legacy",
}
_ALLOWED_PERSONA_MEMORY_WRITE_MODES = {
    "legacy_only",
    "chacha_only",
    "dual_write",
}
_CHACHA_RETRIEVABLE_MEMORY_TYPES = {
    "summary",
    "semantic",
    "legacy_semantic",
}


@dataclass
class RetrievedMemory:
    content: str
    memory_id: str | None = None


@dataclass
class PersonaMemoryBackfillResult:
    processed_semantic: int
    inserted_semantic: int
    skipped_semantic: int
    processed_usage_events: int
    inserted_usage_events: int
    skipped_usage_events: int
    next_checkpoint: dict[str, int]
    completed: bool


def _normalize_personalization_user_id(user_id: str) -> str:
    raw = str(user_id or "").strip()
    if not raw:
        raise ValueError("user_id is required")
    if raw.isdigit():
        return str(int(raw))
    digest = hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).digest()
    return str(int.from_bytes(digest[:4], byteorder="big", signed=False))


def _get_db_for_user(user_id: str) -> tuple[PersonalizationDB, str]:
    normalized_user_id = _normalize_personalization_user_id(user_id)
    db_path = DatabasePaths.get_personalization_db_path(int(normalized_user_id))
    return PersonalizationDB(str(db_path)), normalized_user_id


def _open_chacha_db_for_user(user_id: str) -> tuple[CharactersRAGDB, str]:
    normalized_user_id = _normalize_personalization_user_id(user_id)
    db_path = DatabasePaths.get_chacha_db_path(normalized_user_id)
    return CharactersRAGDB(str(db_path), client_id=f"persona_memory_{normalized_user_id}"), normalized_user_id


def _is_profile_opted_in(db: PersonalizationDB, normalized_user_id: str) -> bool:
    profile = db.get_or_create_profile(normalized_user_id)
    return bool(profile.get("enabled", 0))


def _coerce_flag_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    candidate = str(value).strip().lower()
    if candidate in {"1", "true", "yes", "on", "enabled"}:
        return True
    if candidate in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def _get_persona_memory_read_mode() -> str:
    try:
        candidate = str(settings.get("PERSONA_MEMORY_READ_MODE", _DEFAULT_PERSONA_MEMORY_READ_MODE)).strip().lower()
    except Exception:
        candidate = _DEFAULT_PERSONA_MEMORY_READ_MODE
    if candidate in _ALLOWED_PERSONA_MEMORY_READ_MODES:
        return candidate
    return _DEFAULT_PERSONA_MEMORY_READ_MODE


def _get_persona_memory_write_mode() -> str:
    try:
        candidate = str(settings.get("PERSONA_MEMORY_WRITE_MODE", _DEFAULT_PERSONA_MEMORY_WRITE_MODE)).strip().lower()
    except Exception:
        candidate = _DEFAULT_PERSONA_MEMORY_WRITE_MODE
    if candidate in _ALLOWED_PERSONA_MEMORY_WRITE_MODES:
        return candidate
    return _DEFAULT_PERSONA_MEMORY_WRITE_MODE


def _ensure_persona_profile_for_memory(
    chacha_db: CharactersRAGDB,
    *,
    user_id: str,
    persona_id: str,
) -> bool:
    profile = chacha_db.get_persona_profile(persona_id, user_id=user_id, include_deleted=False)
    if profile is not None:
        return True
    try:
        _ = chacha_db.create_persona_profile(
            {
                "id": str(persona_id),
                "user_id": str(user_id),
                "name": f"Persona {persona_id}",
                "mode": "session_scoped",
                "system_prompt": "",
                "is_active": True,
            }
        )
        return True
    except ConflictError:
        profile = chacha_db.get_persona_profile(persona_id, user_id=user_id, include_deleted=False)
        return profile is not None
    except (CharactersRAGDBError, OSError, RuntimeError, ValueError) as exc:
        logger.debug("persona memory profile ensure skipped: {}", exc)
        return False


def _write_legacy_persona_turn(
    *,
    user_id: str,
    normalized_user_id: str,
    session_id: str,
    persona_id: str,
    role: str,
    content: str,
    turn_type: str,
    metadata: dict[str, Any] | None,
    store_as_memory: bool,
) -> bool:
    db_path = DatabasePaths.get_personalization_db_path(int(normalized_user_id))
    db = PersonalizationDB(str(db_path))
    clean_metadata = dict(metadata or {})
    clean_metadata["persona_id"] = str(persona_id or "")
    clean_metadata["turn_type"] = str(turn_type or "text")
    clean_metadata["content_length"] = len(str(content or ""))
    _ = db.insert_usage_event(
        UsageEvent(
            user_id=normalized_user_id,
            type="persona.turn",
            resource_id=str(session_id or ""),
            tags=["persona", str(role or "unknown")],
            metadata=clean_metadata,
        )
    )
    if store_as_memory:
        memory_text = str(content or "").strip()
        if memory_text:
            if len(memory_text) > 1024:
                memory_text = memory_text[:1024]
            _ = db.add_semantic_memory(
                SemanticMemory(
                    user_id=normalized_user_id,
                    content=memory_text,
                    tags=["persona", str(role or "unknown"), str(persona_id or "")],
                    pinned=False,
                )
            )
    return True


def _write_chacha_persona_turn(
    *,
    user_id: str,
    normalized_user_id: str,
    session_id: str,
    persona_id: str,
    role: str,
    content: str,
    turn_type: str,
    metadata: dict[str, Any] | None,
    store_as_memory: bool,
) -> bool:
    chacha_db = None
    try:
        chacha_db, _ = _open_chacha_db_for_user(user_id)
        if not _ensure_persona_profile_for_memory(chacha_db, user_id=normalized_user_id, persona_id=persona_id):
            return False

        telemetry_payload = {
            "role": str(role or "unknown"),
            "turn_type": str(turn_type or "text"),
            "session_id": str(session_id or ""),
            "persona_id": str(persona_id or ""),
            "content_length": len(str(content or "")),
            "metadata": dict(metadata or {}),
        }
        _ = chacha_db.add_persona_memory_entry(
            {
                "persona_id": str(persona_id),
                "user_id": str(normalized_user_id),
                "memory_type": "usage_event",
                "content": json.dumps(telemetry_payload, ensure_ascii=True, sort_keys=True),
                "salience": 0.0,
            }
        )
        if store_as_memory:
            memory_text = str(content or "").strip()
            if memory_text:
                if len(memory_text) > 1024:
                    memory_text = memory_text[:1024]
                _ = chacha_db.add_persona_memory_entry(
                    {
                        "persona_id": str(persona_id),
                        "user_id": str(normalized_user_id),
                        "memory_type": "summary",
                        "content": memory_text,
                        "salience": 0.5,
                    }
                )
        return True
    except (CharactersRAGDBError, OSError, RuntimeError, ValueError, ConflictError) as exc:
        logger.debug("persona chacha memory write skipped: {}", exc)
        return False
    finally:
        if chacha_db is not None:
            try:
                chacha_db.close_all_connections()
                chacha_db.close_connection()
            except Exception as close_exc:
                logger.debug("persona chacha memory close skipped: {}", close_exc)


def _read_legacy_memories(
    *,
    user_id: str,
    normalized_user_id: str,
    query_text: str,
    top_k: int,
) -> list[RetrievedMemory]:
    db_path = DatabasePaths.get_personalization_db_path(int(normalized_user_id))
    db = PersonalizationDB(str(db_path))
    safe_top_k = max(1, min(int(top_k), 10))
    query = str(query_text or "").strip() or None
    items, _ = db.list_semantic_memories(
        user_id=normalized_user_id,
        q=query,
        limit=safe_top_k,
        offset=0,
    )
    if not items and query:
        items, _ = db.list_semantic_memories(
            user_id=normalized_user_id,
            q=None,
            limit=safe_top_k,
            offset=0,
        )
    out: list[RetrievedMemory] = []
    for item in items:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        memory_id = item.get("id")
        out.append(
            RetrievedMemory(
                content=content,
                memory_id=(str(memory_id) if memory_id is not None else None),
            )
        )
    return out


def _read_chacha_memories(
    *,
    user_id: str,
    normalized_user_id: str,
    persona_id: str | None,
    query_text: str,
    top_k: int,
) -> list[RetrievedMemory]:
    chacha_db = None
    try:
        chacha_db, _ = _open_chacha_db_for_user(user_id)
        candidate_limit = max(25, min(500, int(top_k) * 25))
        rows = chacha_db.list_persona_memory_entries(
            user_id=str(normalized_user_id),
            persona_id=(str(persona_id).strip() if persona_id else None),
            include_archived=False,
            include_deleted=False,
            limit=candidate_limit,
            offset=0,
        )
        query = str(query_text or "").strip().lower()
        retrievable_rows = [
            row for row in rows
            if str(row.get("memory_type") or "").strip().lower() in _CHACHA_RETRIEVABLE_MEMORY_TYPES
        ]
        if query:
            filtered = [
                row for row in retrievable_rows
                if query in str(row.get("content") or "").strip().lower()
            ]
            if filtered:
                retrievable_rows = filtered

        out: list[RetrievedMemory] = []
        for row in retrievable_rows[: max(1, min(int(top_k), 10))]:
            content = str(row.get("content") or "").strip()
            if not content:
                continue
            memory_id = row.get("id")
            out.append(
                RetrievedMemory(
                    content=content,
                    memory_id=(str(memory_id) if memory_id is not None else None),
                )
            )
        return out
    except (CharactersRAGDBError, OSError, RuntimeError, ValueError) as exc:
        logger.debug("persona chacha memory retrieval skipped: {}", exc)
        return []
    finally:
        if chacha_db is not None:
            try:
                chacha_db.close_all_connections()
                chacha_db.close_connection()
            except Exception as close_exc:
                logger.debug("persona chacha memory close skipped: {}", close_exc)


def _deterministic_backfill_entry_id(*parts: str) -> str:
    joined = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha1(joined.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"persona_mem_{digest[:24]}"


def _is_unique_entry_conflict(exc: Exception) -> bool:
    message = str(exc).strip().lower()
    if "unique constraint failed" in message:
        return True
    if "duplicate key value violates unique constraint" in message:
        return True
    return False


def _coerce_backfill_checkpoint(checkpoint: dict[str, Any] | None) -> tuple[int, int]:
    if not isinstance(checkpoint, dict):
        return 0, 0
    try:
        semantic_offset = max(0, int(checkpoint.get("semantic_offset", 0)))
    except (TypeError, ValueError):
        semantic_offset = 0
    try:
        events_offset = max(0, int(checkpoint.get("events_offset", 0)))
    except (TypeError, ValueError):
        events_offset = 0
    return semantic_offset, events_offset


def retrieve_top_memories(
    *,
    user_id: str | None,
    query_text: str,
    top_k: int = 3,
    persona_id: str | None = None,
) -> list[RetrievedMemory]:
    if not user_id or not is_personalization_enabled():
        return []
    try:
        legacy_db, normalized_user_id = _get_db_for_user(user_id)
        if not _is_profile_opted_in(legacy_db, normalized_user_id):
            return []

        read_mode = _get_persona_memory_read_mode()
        if read_mode == "chacha_only":
            return _read_chacha_memories(
                user_id=user_id,
                normalized_user_id=normalized_user_id,
                persona_id=persona_id,
                query_text=query_text,
                top_k=top_k,
            )
        if read_mode == "chacha_first_fallback_legacy":
            chacha_result = _read_chacha_memories(
                user_id=user_id,
                normalized_user_id=normalized_user_id,
                persona_id=persona_id,
                query_text=query_text,
                top_k=top_k,
            )
            if chacha_result:
                return chacha_result
            return _read_legacy_memories(
                user_id=user_id,
                normalized_user_id=normalized_user_id,
                query_text=query_text,
                top_k=top_k,
            )
        return _read_legacy_memories(
            user_id=user_id,
            normalized_user_id=normalized_user_id,
            query_text=query_text,
            top_k=top_k,
        )
    except Exception as exc:
        logger.debug(f"persona memory retrieval skipped: {exc}")
        return []


def persist_persona_turn(
    *,
    user_id: str | None,
    session_id: str,
    persona_id: str,
    role: str,
    content: str,
    turn_type: str,
    metadata: dict[str, Any] | None = None,
    store_as_memory: bool = False,
) -> bool:
    if not user_id or not is_personalization_enabled():
        return False
    try:
        legacy_db, normalized_user_id = _get_db_for_user(user_id)
        if not _is_profile_opted_in(legacy_db, normalized_user_id):
            return False

        write_mode = _get_persona_memory_write_mode()
        legacy_ok = False
        chacha_ok = False

        if write_mode in {"legacy_only", "dual_write"}:
            legacy_ok = _write_legacy_persona_turn(
                user_id=user_id,
                normalized_user_id=normalized_user_id,
                session_id=session_id,
                persona_id=persona_id,
                role=role,
                content=content,
                turn_type=turn_type,
                metadata=metadata,
                store_as_memory=bool(store_as_memory),
            )
        if write_mode in {"chacha_only", "dual_write"}:
            chacha_ok = _write_chacha_persona_turn(
                user_id=user_id,
                normalized_user_id=normalized_user_id,
                session_id=session_id,
                persona_id=persona_id,
                role=role,
                content=content,
                turn_type=turn_type,
                metadata=metadata,
                store_as_memory=bool(store_as_memory),
            )

        if write_mode == "dual_write":
            return legacy_ok or chacha_ok
        if write_mode == "chacha_only":
            return chacha_ok
        return legacy_ok
    except Exception as exc:
        logger.debug(f"persona turn persistence skipped: {exc}")
        return False


def persist_tool_outcome(
    *,
    user_id: str | None,
    session_id: str,
    persona_id: str,
    tool_name: str,
    step_idx: int,
    outcome: dict[str, Any],
    store_as_memory: bool = True,
) -> bool:
    try:
        serialized = json.dumps(outcome, ensure_ascii=True, sort_keys=True)
    except Exception:
        serialized = str(outcome)
    tool_summary = f"Tool={tool_name} step={step_idx} outcome={serialized}"
    return persist_persona_turn(
        user_id=user_id,
        session_id=session_id,
        persona_id=persona_id,
        role="tool",
        content=tool_summary,
        turn_type="tool_result",
        metadata={"tool_name": str(tool_name or ""), "step_idx": int(step_idx)},
        store_as_memory=bool(store_as_memory),
    )


def backfill_persona_memory_from_legacy(
    *,
    user_id: str | None,
    persona_id: str,
    batch_size: int = 100,
    checkpoint: dict[str, Any] | None = None,
    include_usage_events: bool = True,
) -> PersonaMemoryBackfillResult:
    """
    Backfill legacy personalization data to ChaCha persona memory entries.

    The operation is idempotent (deterministic IDs), resumable (checkpoint offsets),
    and opt-in gated (uses legacy personalization profile enabled state).
    """
    empty_result = PersonaMemoryBackfillResult(
        processed_semantic=0,
        inserted_semantic=0,
        skipped_semantic=0,
        processed_usage_events=0,
        inserted_usage_events=0,
        skipped_usage_events=0,
        next_checkpoint={"semantic_offset": 0, "events_offset": 0},
        completed=True,
    )
    if not user_id or not is_personalization_enabled():
        return empty_result

    safe_batch = max(1, min(int(batch_size), 1000))
    semantic_offset, events_offset = _coerce_backfill_checkpoint(checkpoint)

    chacha_db = None
    try:
        legacy_db, normalized_user_id = _get_db_for_user(user_id)
        if not _is_profile_opted_in(legacy_db, normalized_user_id):
            return empty_result
        chacha_db, _ = _open_chacha_db_for_user(user_id)
        if not _ensure_persona_profile_for_memory(chacha_db, user_id=normalized_user_id, persona_id=persona_id):
            return empty_result

        processed_semantic = 0
        inserted_semantic = 0
        skipped_semantic = 0

        semantic_items, _ = legacy_db.list_semantic_memories(
            user_id=normalized_user_id,
            q=None,
            limit=safe_batch,
            offset=semantic_offset,
            include_hidden=True,
        )
        for item in semantic_items:
            processed_semantic += 1
            legacy_memory_id = str(item.get("id") or "")
            entry_id = _deterministic_backfill_entry_id(
                "legacy_semantic",
                normalized_user_id,
                persona_id,
                legacy_memory_id,
            )
            content = str(item.get("content") or "").strip()
            if not content:
                skipped_semantic += 1
                continue
            try:
                _ = chacha_db.add_persona_memory_entry(
                    {
                        "id": entry_id,
                        "persona_id": str(persona_id),
                        "user_id": str(normalized_user_id),
                        "memory_type": "legacy_semantic",
                        "content": content[:1024],
                        "salience": 0.8 if bool(item.get("pinned")) else 0.4,
                    }
                )
                inserted_semantic += 1
            except Exception as exc:
                if _is_unique_entry_conflict(exc):
                    skipped_semantic += 1
                    continue
                raise

        processed_usage_events = 0
        inserted_usage_events = 0
        skipped_usage_events = 0
        usage_batch: list[dict[str, Any]] = []
        if include_usage_events and len(semantic_items) < safe_batch:
            usage_batch = legacy_db.list_recent_events(
                user_id=normalized_user_id,
                limit=safe_batch,
                offset=events_offset,
            )
            for event in usage_batch:
                processed_usage_events += 1
                legacy_event_id = str(event.get("id") or "")
                entry_id = _deterministic_backfill_entry_id(
                    "legacy_usage_event",
                    normalized_user_id,
                    persona_id,
                    legacy_event_id,
                )
                payload = {
                    "id": legacy_event_id,
                    "timestamp": event.get("timestamp"),
                    "type": event.get("type"),
                    "resource_id": event.get("resource_id"),
                    "tags": event.get("tags") or [],
                }
                try:
                    _ = chacha_db.add_persona_memory_entry(
                        {
                            "id": entry_id,
                            "persona_id": str(persona_id),
                            "user_id": str(normalized_user_id),
                            "memory_type": "legacy_usage_event",
                            "content": json.dumps(payload, ensure_ascii=True, sort_keys=True),
                            "salience": 0.0,
                            "archived": True,
                        }
                    )
                    inserted_usage_events += 1
                except Exception as exc:
                    if _is_unique_entry_conflict(exc):
                        skipped_usage_events += 1
                        continue
                    raise

        next_semantic_offset = semantic_offset + len(semantic_items)
        next_events_offset = events_offset
        if include_usage_events and len(semantic_items) < safe_batch:
            next_events_offset = events_offset + len(usage_batch)
        completed = (
            len(semantic_items) < safe_batch
            and (
                not include_usage_events
                or len(usage_batch) < safe_batch
            )
        )
        return PersonaMemoryBackfillResult(
            processed_semantic=processed_semantic,
            inserted_semantic=inserted_semantic,
            skipped_semantic=skipped_semantic,
            processed_usage_events=processed_usage_events,
            inserted_usage_events=inserted_usage_events,
            skipped_usage_events=skipped_usage_events,
            next_checkpoint={
                "semantic_offset": next_semantic_offset,
                "events_offset": next_events_offset,
            },
            completed=completed,
        )
    except Exception as exc:
        logger.debug("persona memory backfill skipped: {}", exc)
        return empty_result
    finally:
        if chacha_db is not None:
            try:
                chacha_db.close_all_connections()
                chacha_db.close_connection()
            except Exception as close_exc:
                logger.debug("persona memory backfill close skipped: {}", close_exc)
