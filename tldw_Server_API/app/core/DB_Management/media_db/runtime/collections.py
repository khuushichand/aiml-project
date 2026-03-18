"""Optional collections integration loaders for Media DB runtime helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def load_collections_database_cls() -> Any | None:
    try:
        module = import_module("tldw_Server_API.app.core.DB_Management.Collections_DB")
    except ImportError:
        return None

    return getattr(module, "CollectionsDatabase", None)


__all__ = ["load_collections_database_cls"]
