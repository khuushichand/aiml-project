"""Legacy read helpers extracted from the media DB shim."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError
from tldw_Server_API.app.core.DB_Management.media_db.runtime.validation import (
    MediaDbLike,
    require_media_database_like,
)


def get_media_transcripts(
    db_instance: MediaDbLike,
    media_id: int,
) -> list[dict]:
    """Return undeleted transcript rows for a media item, newest first."""
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance required.",
    )
    try:
        query = (
            "SELECT t.* FROM Transcripts t "
            "JOIN Media m ON t.media_id = m.id "
            "WHERE t.media_id = ? AND t.deleted = 0 AND m.deleted = 0 "
            "ORDER BY t.created_at DESC"
        )
        with db_instance.transaction() as conn:
            rows = db_instance._fetchall_with_connection(conn, query, (media_id,))
    except (DatabaseError, sqlite3.Error) as exc:
        logger.exception(
            f"Error getting transcripts media {media_id} '{db_instance.db_path_str}'"
        )
        raise DatabaseError(f"Failed get transcripts {media_id}") from exc  # noqa: TRY003
    else:
        return rows


def get_latest_transcription(
    db_instance: MediaDbLike,
    media_id: int,
) -> str | None:
    """Return the most recent transcript text for a media item, if present."""
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance required.",
    )
    try:
        query = (
            "SELECT t.transcription FROM Transcripts t "
            "JOIN Media m ON t.media_id = m.id "
            "WHERE t.media_id = ? AND t.deleted = 0 AND m.deleted = 0 "
            "ORDER BY t.created_at DESC LIMIT 1"
        )
        with db_instance.transaction() as conn:
            result = db_instance._fetchone_with_connection(conn, query, (media_id,))
        raw = (result or {}).get("transcription")
        if raw is None:
            return None
        if isinstance(raw, dict):
            text_val = raw.get("text")
            if text_val is None:
                return ""
            return text_val if isinstance(text_val, str) else str(text_val)
        if isinstance(raw, str):
            stripped = raw.lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    return raw
                if isinstance(data, dict):
                    text_val = data.get("text")
                    if text_val is None:
                        return ""
                    return text_val if isinstance(text_val, str) else str(text_val)
            return raw
        return str(raw)
    except (DatabaseError, sqlite3.Error) as exc:
        logger.exception(
            f"Error get latest transcript {media_id} '{db_instance.db_path_str}'"
        )
        raise DatabaseError(f"Failed get latest transcript {media_id}") from exc  # noqa: TRY003


def get_specific_transcript(
    db_instance: MediaDbLike,
    transcript_uuid: str,
) -> dict[str, Any] | None:
    """Return a specific undeleted transcript row by UUID."""
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance required.",
    )
    try:
        query = (
            "SELECT t.* FROM Transcripts t "
            "JOIN Media m ON t.media_id = m.id "
            "WHERE t.uuid = ? AND t.deleted = 0 AND m.deleted = 0"
        )
        with db_instance.transaction() as conn:
            result = db_instance._fetchone_with_connection(conn, query, (transcript_uuid,))
    except (DatabaseError, sqlite3.Error) as exc:
        logger.exception(
            f"Error get transcript UUID {transcript_uuid} '{db_instance.db_path_str}'"
        )
        raise DatabaseError(f"Failed get transcript {transcript_uuid}") from exc  # noqa: TRY003
    else:
        return result


def get_media_prompts(
    db_instance: MediaDbLike,
    media_id: int,
) -> list[dict]:
    """Return prompt-bearing document versions for a media item."""
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance required.",
    )
    try:
        query = (
            "SELECT dv.id, dv.uuid, dv.prompt, dv.created_at, dv.version_number "
            "FROM DocumentVersions dv JOIN Media m ON dv.media_id = m.id "
            "WHERE dv.media_id = ? AND dv.deleted = 0 AND m.deleted = 0 "
            "AND dv.prompt IS NOT NULL AND dv.prompt != '' "
            "ORDER BY dv.version_number DESC"
        )
        with db_instance.transaction() as conn:
            rows = db_instance._fetchall_with_connection(conn, query, (media_id,))
        return [
            {
                "id": row["id"],
                "uuid": row["uuid"],
                "content": row["prompt"],
                "created_at": row["created_at"],
                "version_number": row["version_number"],
            }
            for row in rows
        ]
    except (DatabaseError, sqlite3.Error) as exc:
        logger.exception(
            f"Error get prompts media {media_id} '{db_instance.db_path_str}'"
        )
        raise DatabaseError(f"Failed get prompts {media_id}") from exc  # noqa: TRY003


def get_specific_prompt(
    db_instance: MediaDbLike,
    version_uuid: str,
) -> str | None:
    """Return the prompt stored for a specific undeleted document version."""
    db_instance = require_media_database_like(
        db_instance,
        error_message="db_instance required.",
    )
    try:
        query = (
            "SELECT dv.prompt FROM DocumentVersions dv "
            "JOIN Media m ON dv.media_id = m.id "
            "WHERE dv.uuid = ? AND dv.deleted = 0 AND m.deleted = 0"
        )
        with db_instance.transaction() as conn:
            result = db_instance._fetchone_with_connection(conn, query, (version_uuid,))
        return (result or {}).get("prompt")
    except (DatabaseError, sqlite3.Error) as exc:
        logger.exception(
            f"Error get prompt UUID {version_uuid} '{db_instance.db_path_str}'"
        )
        raise DatabaseError(f"Failed get prompt {version_uuid}") from exc  # noqa: TRY003


__all__ = [
    "get_latest_transcription",
    "get_media_prompts",
    "get_media_transcripts",
    "get_specific_prompt",
    "get_specific_transcript",
]
