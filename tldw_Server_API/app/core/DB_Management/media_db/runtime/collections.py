"""Optional collections integration loaders for Media DB runtime helpers."""

from __future__ import annotations

from importlib import import_module


def load_collections_database_cls() -> type[object] | None:
    """Return the optional ``CollectionsDatabase`` class when that module exists.

    The collections subsystem is optional for Media DB consumers. When the
    ``Collections_DB`` module is absent, this loader returns ``None``. Import
    errors raised *inside* that module are re-raised so broken optional wiring
    does not get silently masked.
    """

    module_path = "tldw_Server_API.app.core.DB_Management.Collections_DB"
    try:
        module = import_module(module_path)
    except ModuleNotFoundError as exc:
        if exc.name is None or (
            exc.name != module_path and not module_path.startswith(f"{exc.name}.")
        ):
            raise
        return None

    candidate = getattr(module, "CollectionsDatabase", None)
    return candidate if isinstance(candidate, type) else None


__all__ = ["load_collections_database_cls"]
