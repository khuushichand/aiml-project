"""PostgreSQL migration body for schema v21 structure/visual indexes."""

from __future__ import annotations

from typing import Any, Protocol


class _IndexBackend(Protocol):
    """Backend surface required by the v21 migration body."""

    def escape_identifier(self, name: str) -> str: ...

    def table_exists(self, table_name: str, *, connection: Any) -> bool: ...

    def execute(self, query: str, *, connection: Any) -> Any: ...


class PostgresStructureVisualIndexBody(Protocol):
    """DB surface required by the v21 migration helper."""

    @property
    def backend(self) -> _IndexBackend: ...


def run_postgres_migrate_to_v21(db: PostgresStructureVisualIndexBody, conn: Any) -> None:
    """Add structure and visual lookup indexes introduced in schema v21."""

    backend = db.backend
    ident = backend.escape_identifier

    structure_table: str | None = None
    if backend.table_exists("documentstructureindex", connection=conn):
        structure_table = "documentstructureindex"
    elif backend.table_exists("DocumentStructureIndex", connection=conn):
        structure_table = "DocumentStructureIndex"
    if structure_table:
        backend.execute(
            (
                f"CREATE INDEX IF NOT EXISTS {ident('idx_dsi_media_path')} "
                f"ON {ident(structure_table)} ({ident('media_id')}, {ident('path')})"
            ),
            connection=conn,
        )

    visual_documents_table: str | None = None
    if backend.table_exists("visualdocuments", connection=conn):
        visual_documents_table = "visualdocuments"
    elif backend.table_exists("VisualDocuments", connection=conn):
        visual_documents_table = "VisualDocuments"
    if visual_documents_table:
        backend.execute(
            (
                f"CREATE INDEX IF NOT EXISTS {ident('idx_visualdocs_caption')} "
                f"ON {ident(visual_documents_table)} ({ident('caption')})"
            ),
            connection=conn,
        )
        backend.execute(
            (
                f"CREATE INDEX IF NOT EXISTS {ident('idx_visualdocs_tags')} "
                f"ON {ident(visual_documents_table)} ({ident('tags')})"
            ),
            connection=conn,
        )


__all__ = ["PostgresStructureVisualIndexBody", "run_postgres_migrate_to_v21"]
