"""Legacy transcript helpers extracted from the media DB shim."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.errors import (
    ConflictError,
    DatabaseError,
    InputError,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.validation import (
    MediaDbLike,
    require_media_database_like,
)


def soft_delete_transcript(
    db_instance: MediaDbLike,
    transcript_uuid: str,
) -> bool:
    """Soft delete a transcript by UUID and emit the matching sync-log event."""
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance required.",
    )
    if not transcript_uuid:
        raise InputError("Transcript UUID required.")  # noqa: TRY003

    current_time = db_instance._get_current_utc_timestamp_str()
    client_id = db_instance.client_id
    logger.debug(f"Attempting soft delete Transcript UUID: {transcript_uuid}")
    try:
        with db_instance.transaction() as conn:
            info = db_instance._fetchone_with_connection(
                conn,
                "SELECT t.id, t.version, m.uuid as media_uuid FROM Transcripts t JOIN Media m ON t.media_id = m.id "
                "WHERE t.uuid = ? AND t.deleted = 0",
                (transcript_uuid,),
            )
            if not info:
                logger.warning(
                    f"Transcript UUID {transcript_uuid} not found or already deleted."
                )
                return False
            transcript_id = info["id"]
            current_version = info["version"]
            media_uuid = info["media_uuid"]
            new_version = current_version + 1

            update_cursor = db_instance._execute_with_connection(
                conn,
                "UPDATE Transcripts SET deleted=1, last_modified=?, version=?, client_id=? WHERE id=? AND version=?",
                (current_time, new_version, client_id, transcript_id, current_version),
            )
            if update_cursor.rowcount == 0:
                raise ConflictError("Transcripts", transcript_id)  # noqa: TRY301

            payload = {
                "uuid": transcript_uuid,
                "media_uuid": media_uuid,
                "last_modified": current_time,
                "version": new_version,
                "client_id": client_id,
                "deleted": 1,
            }
            db_instance._log_sync_event(
                conn,
                "Transcripts",
                transcript_uuid,
                "delete",
                new_version,
                payload,
            )
            logger.info(
                f"Soft deleted Transcript UUID {transcript_uuid}. New ver: {new_version}"
            )
            return True
    except (InputError, ConflictError, DatabaseError, sqlite3.Error) as exc:
        logger.error(
            f"Error soft delete Transcript UUID {transcript_uuid}: {exc}",
            exc_info=True,
        )
        if isinstance(exc, (InputError, ConflictError, DatabaseError)):
            raise
        raise DatabaseError(f"Failed soft delete transcript: {exc}") from exc  # noqa: TRY003
    except Exception as exc:
        logger.error(
            f"Unexpected soft delete Transcript error UUID {transcript_uuid}: {exc}",
            exc_info=True,
        )
        raise DatabaseError(f"Unexpected transcript soft delete error: {exc}") from exc  # noqa: TRY003


def upsert_transcript(
    db_instance: MediaDbLike,
    media_id: int,
    transcription: str,
    whisper_model: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create or update a transcript row for one media/model pair.

    Args:
        db_instance: Database-like media store handle.
        media_id: Media row identifier associated with the transcript.
        transcription: Transcript content to persist.
        whisper_model: Transcription model identifier.
        created_at: Optional created-at timestamp override.

    Returns:
        Metadata for the created or updated transcript row.

    Raises:
        TypeError: If ``media_id`` is not an integer.
        InputError: If required transcript inputs are missing.
        ConflictError: If optimistic concurrency detects a conflicting update.
        DatabaseError: If the underlying database write fails.
    """
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance required.",
    )
    if not isinstance(media_id, int):
        raise TypeError("media_id must be int")  # noqa: TRY003
    if not transcription:
        raise InputError("transcription text required")  # noqa: TRY003
    if not whisper_model:
        raise InputError("whisper_model required")  # noqa: TRY003

    now = db_instance._get_current_utc_timestamp_str()
    created_val = created_at or now
    client_id = db_instance.client_id

    try:
        with db_instance.transaction() as conn:
            info = db_instance._fetchone_with_connection(
                conn,
                "SELECT id, uuid, version FROM Transcripts WHERE media_id = ? AND whisper_model = ? AND deleted = 0",
                (media_id, whisper_model),
            )

            if info:
                transcript_id = info.get("id")
                transcript_uuid = info.get("uuid")
                current_version = int(info.get("version") or 1)
                new_version = current_version + 1
                update_cursor = db_instance._execute_with_connection(
                    conn,
                    (
                        "UPDATE Transcripts SET transcription = ?, last_modified = ?, version = ?, client_id = ? "
                        "WHERE id = ? AND version = ?"
                    ),
                    (
                        transcription,
                        now,
                        new_version,
                        client_id,
                        transcript_id,
                        current_version,
                    ),
                )
                if update_cursor.rowcount == 0:
                    raise ConflictError("Transcripts", transcript_id)  # noqa: TRY301
                payload = {
                    "id": transcript_id,
                    "uuid": transcript_uuid,
                    "version": new_version,
                    "media_id": media_id,
                    "whisper_model": whisper_model,
                    "last_modified": now,
                }
                db_instance._log_sync_event(
                    conn,
                    "Transcripts",
                    transcript_uuid,
                    "update",
                    new_version,
                    payload,
                )
                return payload

            new_uuid = str(uuid.uuid4())
            if db_instance.backend_type == BackendType.POSTGRESQL:
                insert_sql = (
                    "INSERT INTO Transcripts (media_id, whisper_model, transcription, created_at, uuid, last_modified, version, client_id, deleted) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?, 0) RETURNING id, version"
                )
                cursor = db_instance._execute_with_connection(
                    conn,
                    insert_sql,
                    (media_id, whisper_model, transcription, created_val, new_uuid, now, client_id),
                )
                row = cursor.fetchone()
                new_id = row["id"] if row else None
                new_version = row["version"] if row else 1
            else:
                insert_sql = (
                    "INSERT INTO Transcripts (media_id, whisper_model, transcription, created_at, uuid, last_modified, version, client_id, deleted) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?, 0)"
                )
                cursor = db_instance._execute_with_connection(
                    conn,
                    insert_sql,
                    (media_id, whisper_model, transcription, created_val, new_uuid, now, client_id),
                )
                new_id = cursor.lastrowid
                new_version = 1

            payload = {
                "id": new_id,
                "uuid": new_uuid,
                "version": new_version,
                "media_id": media_id,
                "whisper_model": whisper_model,
                "last_modified": now,
            }
            db_instance._log_sync_event(
                conn,
                "Transcripts",
                new_uuid,
                "create",
                new_version,
                payload,
            )
            return payload
    except (InputError, ConflictError, DatabaseError, sqlite3.Error) as exc:
        if isinstance(exc, (InputError, ConflictError, DatabaseError)):
            raise
        raise DatabaseError(f"Failed upsert transcript: {exc}") from exc  # noqa: TRY003
    except Exception as exc:
        raise DatabaseError(f"Unexpected upsert transcript error: {exc}") from exc  # noqa: TRY003


__all__ = [
    "soft_delete_transcript",
    "upsert_transcript",
]
