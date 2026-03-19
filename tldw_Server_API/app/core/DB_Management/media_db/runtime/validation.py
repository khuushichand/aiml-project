"""Structural validation helpers for Media DB-like objects."""

from __future__ import annotations

from typing import Any


MediaDbLike = Any


def is_media_database_like(candidate: Any) -> bool:
    required_callables = (
        "execute_query",
        "transaction",
        "_fetchall_with_connection",
        "_fetchone_with_connection",
        "_execute_with_connection",
        "_get_current_utc_timestamp_str",
        "_log_sync_event",
    )
    required_attrs = ("client_id", "db_path_str")
    return (
        candidate is not None
        and all(callable(getattr(candidate, name, None)) for name in required_callables)
        and all(getattr(candidate, name, None) is not None for name in required_attrs)
    )


def unwrap_media_database_like(candidate: Any) -> Any:
    if is_media_database_like(candidate):
        return candidate

    wrapped = getattr(candidate, "database", None)
    if is_media_database_like(wrapped):
        return wrapped

    return candidate


def require_media_database_like(
    candidate: Any,
    *,
    error_message: str,
) -> MediaDbLike:
    db_instance = unwrap_media_database_like(candidate)
    if not is_media_database_like(db_instance):
        raise TypeError(error_message)  # noqa: TRY003
    return db_instance


__all__ = [
    "MediaDbLike",
    "is_media_database_like",
    "require_media_database_like",
    "unwrap_media_database_like",
]
