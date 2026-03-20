"""Centralized legacy Media DB compatibility identifiers."""

from __future__ import annotations

LEGACY_MEDIA_DB_BASENAME = "Media_DB_v2"
LEGACY_MEDIA_DB_FILENAME = f"{LEGACY_MEDIA_DB_BASENAME}.db"
LEGACY_MEDIA_DB_MODULE = f"tldw_Server_API.app.core.DB_Management.{LEGACY_MEDIA_DB_BASENAME}"

__all__ = [
    "LEGACY_MEDIA_DB_BASENAME",
    "LEGACY_MEDIA_DB_FILENAME",
    "LEGACY_MEDIA_DB_MODULE",
]
