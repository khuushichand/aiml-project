"""SQLite schema bootstrap implementation for Media DB."""

from __future__ import annotations

from typing import Protocol


class SupportsSqliteSchemaBootstrap(Protocol):
    """Protocol for legacy DB objects that still own SQLite bootstrap logic."""

    def _initialize_schema_sqlite(self) -> None: ...


def initialize_sqlite_schema(db: SupportsSqliteSchemaBootstrap) -> None:
    """Initialize or migrate the SQLite schema using the legacy implementation.

    This remains a transitional bridge to the legacy private schema bootstrap
    method until the SQLite bootstrap logic is fully extracted from the
    compatibility class.
    """

    db._initialize_schema_sqlite()
