"""PostgreSQL sequence maintenance helper."""

from __future__ import annotations

from typing import Any, Protocol


class _SequenceQueryResult(Protocol):
    """Backend query result protocol for sequence metadata scans."""

    rows: list[dict[str, object]]


class _ScalarQueryResult(Protocol):
    """Backend query result protocol for MAX(...) lookups."""

    scalar: object


class _SequenceMaintenanceBackend(Protocol):
    """Backend protocol for PostgreSQL sequence synchronization."""

    def execute(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
        *,
        connection: object,
    ) -> _SequenceQueryResult | _ScalarQueryResult | object: ...

    def escape_identifier(self, value: str) -> str: ...


class PostgresSequenceMaintenanceDB(Protocol):
    """Protocol for DB objects exposing a PostgreSQL backend."""

    backend: _SequenceMaintenanceBackend


def sync_postgres_sequences(
    db: PostgresSequenceMaintenanceDB,
    conn: Any,
) -> None:
    """Align PostgreSQL sequences with current table maxima."""

    backend = db.backend
    sequence_rows = backend.execute(
        """
        SELECT
            sequence_ns.nspname AS sequence_schema,
            seq.relname AS sequence_name,
            tab.relname AS table_name,
            col.attname AS column_name
        FROM pg_class seq
        JOIN pg_namespace sequence_ns ON sequence_ns.oid = seq.relnamespace
        JOIN pg_depend dep ON dep.objid = seq.oid AND dep.deptype = 'a'
        JOIN pg_class tab ON tab.oid = dep.refobjid
        JOIN pg_namespace tab_ns ON tab_ns.oid = tab.relnamespace
        JOIN pg_attribute col ON col.attrelid = tab.oid AND col.attnum = dep.refobjsubid
        WHERE seq.relkind = 'S' AND tab_ns.nspname = 'public';
        """,
        connection=conn,
    )

    for row in sequence_rows.rows:
        table_name = row.get("table_name")
        column_name = row.get("column_name")
        sequence_schema = row.get("sequence_schema", "public")
        sequence_name = row.get("sequence_name")

        if not table_name or not column_name or not sequence_name:
            continue

        qualified_sequence = f"{sequence_schema}.{sequence_name}"
        ident = backend.escape_identifier

        max_result = backend.execute(
            (
                f"SELECT COALESCE(MAX({ident(column_name)}), 0) AS max_id "  # nosec B608
                f"FROM {ident(table_name)}"
            ),
            connection=conn,
        )

        max_id_raw = max_result.scalar
        try:
            max_id = int(max_id_raw or 0)
        except (TypeError, ValueError):
            max_id = 0

        if max_id <= 0:
            backend.execute(
                "SELECT setval(%s, %s, false)",
                (qualified_sequence, 1),
                connection=conn,
            )
        else:
            backend.execute(
                "SELECT setval(%s, %s)",
                (qualified_sequence, max_id),
                connection=conn,
            )


__all__ = [
    "PostgresSequenceMaintenanceDB",
    "sync_postgres_sequences",
]
