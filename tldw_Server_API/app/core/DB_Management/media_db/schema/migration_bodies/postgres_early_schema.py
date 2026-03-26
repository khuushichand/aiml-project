"""PostgreSQL early-schema migration body helpers."""

from __future__ import annotations

from typing import Any, Protocol


class _IdentifierBackend(Protocol):
    def escape_identifier(self, name: str) -> str: ...

    def execute(self, query: str, *, connection: Any) -> None: ...


class PostgresEarlySchemaBody(Protocol):
    """Protocol for DB objects that can run early PostgreSQL schema migrations."""

    backend: _IdentifierBackend


def run_postgres_migrate_to_v5(db: PostgresEarlySchemaBody, conn: Any) -> None:
    """Add ``safe_metadata`` to ``documentversions``."""

    backend = db.backend
    ident = backend.escape_identifier
    backend.execute(
        (
            f"ALTER TABLE {ident('documentversions')} "
            f"ADD COLUMN IF NOT EXISTS {ident('safe_metadata')} TEXT"
        ),
        connection=conn,
    )


def run_postgres_migrate_to_v6(db: PostgresEarlySchemaBody, conn: Any) -> None:
    """Create ``documentversionidentifiers`` and its lookup indexes."""

    backend = db.backend
    ident = backend.escape_identifier
    backend.execute(
        (
            f"CREATE TABLE IF NOT EXISTS {ident('documentversionidentifiers')} ("
            f"{ident('dv_id')} BIGINT PRIMARY KEY REFERENCES {ident('documentversions')}({ident('id')}) ON DELETE CASCADE,"
            f"{ident('doi')} TEXT,"
            f"{ident('pmid')} TEXT,"
            f"{ident('pmcid')} TEXT,"
            f"{ident('arxiv_id')} TEXT,"
            f"{ident('s2_paper_id')} TEXT"
            ")"
        ),
        connection=conn,
    )

    index_defs = [
        ("idx_dvi_doi", "doi"),
        ("idx_dvi_pmid", "pmid"),
        ("idx_dvi_pmcid", "pmcid"),
        ("idx_dvi_arxiv", "arxiv_id"),
        ("idx_dvi_s2", "s2_paper_id"),
    ]

    for index_name, column in index_defs:
        backend.execute(
            (
                f"CREATE INDEX IF NOT EXISTS {ident(index_name)} "
                f"ON {ident('documentversionidentifiers')} ({ident(column)})"
            ),
            connection=conn,
        )


def run_postgres_migrate_to_v7(db: PostgresEarlySchemaBody, conn: Any) -> None:
    """Create ``documentstructureindex`` and its supporting indexes."""

    backend = db.backend
    ident = backend.escape_identifier
    backend.execute(
        (
            f"CREATE TABLE IF NOT EXISTS {ident('documentstructureindex')} ("
            f"{ident('id')} BIGSERIAL PRIMARY KEY,"
            f"{ident('media_id')} BIGINT NOT NULL REFERENCES {ident('media')}({ident('id')}) ON DELETE CASCADE,"
            f"{ident('parent_id')} BIGINT NULL,"
            f"{ident('kind')} TEXT NOT NULL,"
            f"{ident('level')} INTEGER,"
            f"{ident('title')} TEXT,"
            f"{ident('start_char')} BIGINT NOT NULL,"
            f"{ident('end_char')} BIGINT NOT NULL,"
            f"{ident('order_index')} INTEGER,"
            f"{ident('path')} TEXT,"
            f"{ident('created_at')} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            f"{ident('last_modified')} TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            f"{ident('version')} INTEGER NOT NULL DEFAULT 1,"
            f"{ident('client_id')} TEXT NOT NULL,"
            f"{ident('deleted')} BOOLEAN NOT NULL DEFAULT FALSE"
            ")"
        ),
        connection=conn,
    )

    index_defs = [
        ("idx_dsi_media_kind", "media_id, kind"),
        ("idx_dsi_media_start", "media_id, start_char"),
        ("idx_dsi_media_parent", "parent_id"),
    ]
    for name, cols in index_defs:
        backend.execute(
            f"CREATE INDEX IF NOT EXISTS {ident(name)} ON {ident('documentstructureindex')} ({cols})",
            connection=conn,
        )


def run_postgres_migrate_to_v8(db: PostgresEarlySchemaBody, conn: Any) -> None:
    """Add scope columns to ``media`` and ``sync_log``."""

    backend = db.backend
    ident = backend.escape_identifier

    for table in ("media", "sync_log"):
        backend.execute(
            (
                f"ALTER TABLE {ident(table)} "
                f"ADD COLUMN IF NOT EXISTS {ident('org_id')} BIGINT"
            ),
            connection=conn,
        )
        backend.execute(
            (
                f"ALTER TABLE {ident(table)} "
                f"ADD COLUMN IF NOT EXISTS {ident('team_id')} BIGINT"
            ),
            connection=conn,
        )


__all__ = [
    "PostgresEarlySchemaBody",
    "run_postgres_migrate_to_v5",
    "run_postgres_migrate_to_v6",
    "run_postgres_migrate_to_v7",
    "run_postgres_migrate_to_v8",
]
