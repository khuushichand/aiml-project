"""Structural validation helpers for Media DB-like objects."""

from __future__ import annotations

from typing import Any


MediaDbLike = Any


def is_media_database_like(candidate: Any) -> bool:
    return (
        candidate is not None
        and callable(getattr(candidate, "execute_query", None))
        and callable(getattr(candidate, "transaction", None))
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
