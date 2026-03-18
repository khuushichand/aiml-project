"""Loader for the canonical MediaDatabase runtime class."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def load_media_database_cls() -> type[Any]:
    module = import_module("tldw_Server_API.app.core.DB_Management.Media_DB_v2")
    return module.MediaDatabase


__all__ = ["load_media_database_cls"]
