"""Loader for the canonical MediaDatabase runtime class."""

from __future__ import annotations

from importlib import import_module
from typing import Any

NATIVE_MEDIA_DB_MODULE = (
    "tldw_Server_API.app.core.DB_Management.media_db.native_class"
)


def load_media_database_cls() -> type[Any]:
    module = import_module(NATIVE_MEDIA_DB_MODULE)
    return module.MediaDatabase


__all__ = ["load_media_database_cls"]
