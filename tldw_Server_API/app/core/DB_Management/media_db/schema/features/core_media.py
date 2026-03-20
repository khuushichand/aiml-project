"""Core media schema helpers."""

from __future__ import annotations

from typing import Any, Protocol


class SupportsCoreMediaSchema(Protocol):
    """Protocol for legacy DB objects that still own core schema bootstrap."""

    def _apply_schema_v1_sqlite(self, conn: Any) -> None: ...

    def _apply_schema_v1_postgres(self, conn: Any) -> None: ...


def apply_sqlite_core_media_schema(db: SupportsCoreMediaSchema, conn: Any) -> None:
    """Apply the SQLite base schema owned by the legacy Media DB object."""

    db._apply_schema_v1_sqlite(conn)


def apply_postgres_core_media_schema(db: SupportsCoreMediaSchema, conn: Any) -> None:
    """Apply the PostgreSQL base schema owned by the legacy Media DB object."""

    db._apply_schema_v1_postgres(conn)
