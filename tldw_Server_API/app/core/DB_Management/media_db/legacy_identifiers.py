"""Centralized legacy Media DB compatibility identifiers."""

from __future__ import annotations

from tldw_Server_API.app.core.DB_Management.media_db.constants import (
    MEDIA_DB_BASENAME,
    MEDIA_DB_FILENAME,
)

LEGACY_MEDIA_DB_BASENAME = MEDIA_DB_BASENAME
LEGACY_MEDIA_DB_FILENAME = MEDIA_DB_FILENAME
LEGACY_MEDIA_DB_MODULE = "tldw_Server_API.app.core.DB_Management.Media_DB_v2"

__all__ = [
    "LEGACY_MEDIA_DB_BASENAME",
    "LEGACY_MEDIA_DB_FILENAME",
    "LEGACY_MEDIA_DB_MODULE",
]
