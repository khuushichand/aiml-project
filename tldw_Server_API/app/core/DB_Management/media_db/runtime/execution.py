"""Execution helpers for extracted media DB runtime modules."""

from __future__ import annotations

from contextlib import suppress
from typing import Any


def close_sqlite_ephemeral(cursor: Any | None, connection: Any | None) -> None:
    """Best-effort close for ephemeral sqlite cursor/connection pairs."""
    if cursor is not None:
        with suppress(Exception):
            cursor.close()
    if connection is not None:
        with suppress(Exception):
            connection.close()
