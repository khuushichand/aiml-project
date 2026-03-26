"""Small query utility helpers for the package-native Media DB runtime."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.backends.query_utils import (
    convert_sqlite_placeholders_to_postgres,
)


def _keyword_order_expression(self: Any, column: str) -> str:
    """Return backend-aware ORDER BY expression for keyword-like text."""
    if self.backend_type == BackendType.SQLITE:
        return f"{column} COLLATE NOCASE"
    return f"LOWER({column}), {column}"


def _append_case_insensitive_like(
    self: Any,
    clauses: list[str],
    params: list[Any],
    column: str,
    pattern: str,
) -> None:
    """Append backend-aware case-insensitive LIKE predicate and parameter."""
    if self.backend_type == BackendType.POSTGRESQL:
        clauses.append(f"{column} ILIKE ?")
    else:
        clauses.append(f"{column} LIKE ? COLLATE NOCASE")
    params.append(pattern)


def _convert_sqlite_placeholders_to_postgres(self: Any, query: str) -> str:
    """Convert SQLite parameter placeholders to PostgreSQL placeholders."""
    return convert_sqlite_placeholders_to_postgres(query)


__all__ = [
    "_append_case_insensitive_like",
    "_convert_sqlite_placeholders_to_postgres",
    "_keyword_order_expression",
]
