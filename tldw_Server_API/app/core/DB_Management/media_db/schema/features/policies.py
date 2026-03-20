"""Policy schema helpers."""

from __future__ import annotations

from typing import Any, Protocol


class SupportsPostgresPolicies(Protocol):
    """Protocol for legacy DB objects that still own PostgreSQL RLS setup."""

    def _ensure_postgres_rls(self, conn: Any) -> None: ...


def ensure_postgres_policies(db: SupportsPostgresPolicies, conn: Any) -> None:
    """Ensure the PostgreSQL row-level security policies owned by the legacy DB object."""

    db._ensure_postgres_rls(conn)
