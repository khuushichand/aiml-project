"""PostgreSQL visibility/owner migration body helpers."""

from __future__ import annotations

from loguru import logger
from typing import Any, Protocol

from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


class _VisibilityOwnerBackend(Protocol):
    def escape_identifier(self, name: str) -> str: ...

    def execute(self, query: str, *, connection: Any) -> None: ...


class PostgresVisibilityOwnerBody(Protocol):
    """Protocol for DB objects that can run PostgreSQL visibility-owner migration logic."""

    backend: _VisibilityOwnerBackend


def run_postgres_migrate_to_v9(db: PostgresVisibilityOwnerBody, conn: Any) -> None:
    """Run the PostgreSQL visibility-owner migration body."""

    backend = db.backend
    ident = backend.escape_identifier

    backend.execute(
        f"ALTER TABLE {ident('media')} ADD COLUMN IF NOT EXISTS {ident('visibility')} TEXT DEFAULT 'personal'",
        connection=conn,
    )

    media_table_ident = ident("media")
    visibility_col_ident = ident("visibility")
    visibility_constraint_template = """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'chk_media_visibility'
                          AND conrelid = 'media'::regclass
                    ) THEN
                        ALTER TABLE {media_table}
                        ADD CONSTRAINT chk_media_visibility
                        CHECK ({visibility_col} IN ('personal', 'team', 'org'));
                    END IF;
                END $$;
                """
    visibility_constraint_sql = visibility_constraint_template.format(
        media_table=media_table_ident,
        visibility_col=visibility_col_ident,
    )  # nosec B608
    try:
        backend.execute(
            visibility_constraint_sql,
            connection=conn,
        )
    except MEDIA_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(
            "Could not add visibility check constraint: %s",
            exc,
        )

    backend.execute(
        f"ALTER TABLE {ident('media')} ADD COLUMN IF NOT EXISTS {ident('owner_user_id')} BIGINT",
        connection=conn,
    )

    owner_user_id_col_ident = ident("owner_user_id")
    client_id_col_ident = ident("client_id")
    owner_backfill_template = """
                UPDATE {media_table}
                SET {owner_user_id_col} = CAST({client_id_col} AS BIGINT)
                WHERE {owner_user_id_col} IS NULL
                  AND {client_id_col} ~ '^[0-9]+$'
                """
    owner_backfill_sql = owner_backfill_template.format(
        media_table=media_table_ident,
        owner_user_id_col=owner_user_id_col_ident,
        client_id_col=client_id_col_ident,
    )  # nosec B608
    try:
        backend.execute(
            owner_backfill_sql,
            connection=conn,
        )
    except MEDIA_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(
            "Could not backfill owner_user_id: %s",
            exc,
        )

    backend.execute(
        f"CREATE INDEX IF NOT EXISTS idx_media_visibility ON {ident('media')}({ident('visibility')})",
        connection=conn,
    )
    backend.execute(
        f"CREATE INDEX IF NOT EXISTS idx_media_owner_user_id ON {ident('media')}({ident('owner_user_id')})",
        connection=conn,
    )


__all__ = [
    "PostgresVisibilityOwnerBody",
    "run_postgres_migrate_to_v9",
]
