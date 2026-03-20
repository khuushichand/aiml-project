"""Loader for the canonical MediaDatabase runtime class."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db.legacy_identifiers import (
    LEGACY_MEDIA_DB_MODULE,
)


def load_media_database_cls() -> type[Any]:
    module = import_module(LEGACY_MEDIA_DB_MODULE)
    return module.MediaDatabase


__all__ = ["load_media_database_cls"]
