"""Legacy full-media detail helpers extracted from Media_DB_v2."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import TYPE_CHECKING, Any

import yaml
from loguru import logger

from tldw_Server_API.app.core.DB_Management.backends.base import (
    DatabaseError as BackendDatabaseError,
)
from tldw_Server_API.app.core.DB_Management.db_migration import MigrationError
from tldw_Server_API.app.core.DB_Management.media_db.errors import (
    ConflictError,
    DatabaseError,
    InputError,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_content_queries import (
    fetch_keywords_for_media,
)
from tldw_Server_API.app.core.DB_Management.media_db.legacy_wrappers import (
    get_document_version,
)

if TYPE_CHECKING:
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


_MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    AttributeError,
    BackendDatabaseError,
    ConflictError,
    DatabaseError,
    InputError,
    MigrationError,
    KeyError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
    json.JSONDecodeError,
    sqlite3.Error,
    yaml.YAMLError,
)


def _require_media_db_instance(
    db_instance: Any,
    *,
    error_message: str,
) -> "MediaDatabase":
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase

    if not isinstance(db_instance, MediaDatabase):
        raise TypeError(error_message)  # noqa: TRY003
    return db_instance


def get_full_media_details(
    db_instance: "MediaDatabase",
    media_id: int,
    *,
    include_content: bool = True,
) -> dict[str, Any] | None:
    db_instance = _require_media_db_instance(
        db_instance,
        error_message="db_instance required.",
    )
    media = db_instance.get_media_by_id(media_id, include_deleted=False, include_trash=False)
    if not media:
        return None

    latest = get_document_version(
        db_instance,
        media_id=media_id,
        version_number=None,
        include_content=include_content,
    )
    try:
        keywords = fetch_keywords_for_media(media_id=media_id, db_instance=db_instance)
    except _MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS:
        keywords = []

    return {
        "media": media,
        "latest_version": latest,
        "keywords": keywords,
    }


def get_full_media_details_rich(
    db_instance: "MediaDatabase",
    media_id: int,
    *,
    include_content: bool = True,
    include_versions: bool = True,
    include_version_content: bool = False,
) -> dict[str, Any] | None:
    db_instance = _require_media_db_instance(
        db_instance,
        error_message="db_instance required.",
    )
    media = db_instance.get_media_by_id(media_id, include_deleted=False, include_trash=False)
    if not media:
        return None

    latest = get_document_version(
        db_instance,
        media_id=media_id,
        version_number=None,
        include_content=False,
    )
    prompt = (latest or {}).get("prompt")
    analysis = (latest or {}).get("analysis_content")
    safe_metadata_raw = (latest or {}).get("safe_metadata")
    safe_metadata = None
    if isinstance(safe_metadata_raw, str):
        try:
            safe_metadata = json.loads(safe_metadata_raw)
        except _MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS:
            safe_metadata = None
    elif isinstance(safe_metadata_raw, dict):
        safe_metadata = safe_metadata_raw

    try:
        keywords = fetch_keywords_for_media(media_id=media_id, db_instance=db_instance)
    except _MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS:
        keywords = []

    content_text = media.get("content") or ""
    content_meta: dict[str, Any] = {}
    media_type = media.get("type")
    if media_type in ("video", "audio") and content_text:
        try:
            parts = content_text.split("\n\n", 1)
            if len(parts) == 2:
                possible_json_str, remaining_text = parts[0], parts[1]
                try:
                    parsed = json.loads(possible_json_str)
                    if isinstance(parsed, dict):
                        content_meta = parsed
                        content_text = remaining_text
                except _MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS:
                    pass
        except _MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS:
            pass
    word_count = len(content_text.split()) if content_text else 0

    versions_list: list[dict[str, Any]] = []
    if include_versions:
        try:
            rows = db_instance.get_all_document_versions(
                media_id=media_id,
                include_content=include_version_content,
                include_deleted=False,
            )
            for raw_version in rows or []:
                safe_md = raw_version.get("safe_metadata")
                if isinstance(safe_md, str):
                    try:
                        safe_md = json.loads(safe_md)
                    except _MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS:
                        safe_md = None
                created_at_val = raw_version.get("created_at")
                if isinstance(created_at_val, str):
                    try:
                        created_at_val = datetime.fromisoformat(
                            created_at_val.replace("Z", "+00:00")
                        )
                    except _MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS:
                        pass
                versions_list.append(
                    {
                        "uuid": raw_version.get("uuid"),
                        "media_id": raw_version.get("media_id"),
                        "version_number": raw_version.get("version_number"),
                        "created_at": created_at_val,
                        "prompt": raw_version.get("prompt"),
                        "analysis_content": raw_version.get("analysis_content"),
                        "safe_metadata": safe_md,
                        "content": raw_version.get("content") if include_version_content else None,
                    }
                )
        except _MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS:
            versions_list = []

    raw_timestamps = media.get("timestamps", []) or []
    if isinstance(raw_timestamps, str):
        try:
            parsed_ts = json.loads(raw_timestamps)
            raw_timestamps = [str(item) for item in parsed_ts] if isinstance(parsed_ts, list) else []
        except _MEDIA_DETAILS_NONCRITICAL_EXCEPTIONS:
            raw_timestamps = []
    elif isinstance(raw_timestamps, list):
        raw_timestamps = [str(item) for item in raw_timestamps]
    else:
        raw_timestamps = []

    has_original = db_instance.has_original_file(media_id)
    original_file_url = f"/api/v1/media/{media_id}/file" if has_original else None

    return {
        "media_id": media_id,
        "source": {
            "url": media.get("url"),
            "title": media.get("title"),
            "duration": media.get("duration"),
            "type": media_type,
        },
        "processing": {
            "prompt": prompt,
            "analysis": analysis,
            "safe_metadata": safe_metadata,
            "model": media.get("transcription_model"),
            "timestamp_option": media.get("timestamp_option"),
        },
        "content": {
            "metadata": content_meta,
            "text": content_text if include_content else "",
            "word_count": word_count,
        },
        "keywords": keywords,
        "timestamps": raw_timestamps,
        "versions": versions_list,
        "has_original_file": has_original,
        "original_file_url": original_file_url,
    }


__all__ = [
    "get_full_media_details",
    "get_full_media_details_rich",
]
