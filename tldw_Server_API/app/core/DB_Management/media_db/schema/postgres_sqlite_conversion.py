"""SQLite-to-PostgreSQL schema conversion helpers."""

from __future__ import annotations

import re
from typing import Any


def _convert_sqlite_sql_to_postgres_statements(
    db: Any,
    sql: str,
) -> list[str]:
    """Convert a SQLite-oriented SQL blob into Postgres-compatible statements."""

    statements: list[str] = []
    buffer: list[str] = []
    for raw_line in sql.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue
        upper = line.upper()
        if upper.startswith("PRAGMA"):
            continue
        if "VIRTUAL TABLE" in upper and "FTS5" in upper:
            continue
        if upper.startswith("DROP TRIGGER") or upper.startswith("CREATE TRIGGER"):
            continue
        buffer.append(raw_line)
        if line.endswith(";"):
            stmt = "\n".join(buffer)
            buffer = []
            transformed = _transform_sqlite_statement_to_postgres(db, stmt)
            if transformed:
                statements.append(transformed)
    return statements


def _transform_sqlite_statement_to_postgres(
    db: Any,
    statement: str,
) -> str | None:
    """Apply token-level rewrites so a SQLite statement can run on Postgres."""

    del db

    stmt = re.sub(r"--.*?$", "", statement, flags=re.MULTILINE)
    stmt = re.sub(r"/\*.*?\*/", "", stmt, flags=re.DOTALL)
    stmt = stmt.strip()
    if not stmt:
        return None

    upper = stmt.upper()
    if upper.startswith("ANALYZE "):
        return None
    if upper.startswith("PRAGMA "):
        return None

    stmt = re.sub(r"\s+", " ", stmt)

    stmt = re.sub(r"INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY", stmt, flags=re.IGNORECASE)
    stmt = re.sub(r"INTEGER PRIMARY KEY", "BIGINT PRIMARY KEY", stmt, flags=re.IGNORECASE)
    stmt = re.sub(
        r"TEXT\s+DEFAULT\s+\(datetime\('now'\)\)",
        "TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP",
        stmt,
        flags=re.IGNORECASE,
    )
    stmt = re.sub(r"BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE", stmt, flags=re.IGNORECASE)
    stmt = re.sub(r"BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE", stmt, flags=re.IGNORECASE)
    stmt = re.sub(r"BOOLEAN DEFAULT 0", "BOOLEAN DEFAULT FALSE", stmt, flags=re.IGNORECASE)
    stmt = re.sub(r"BOOLEAN DEFAULT 1", "BOOLEAN DEFAULT TRUE", stmt, flags=re.IGNORECASE)
    stmt = re.sub(r"DATETIME", "TIMESTAMPTZ", stmt, flags=re.IGNORECASE)
    stmt = re.sub(r"BLOB", "BYTEA", stmt, flags=re.IGNORECASE)
    stmt = re.sub(r"REAL", "DOUBLE PRECISION", stmt, flags=re.IGNORECASE)
    stmt = re.sub(r"COLLATE NOCASE", "", stmt, flags=re.IGNORECASE)

    stmt = re.sub(r"WHERE deleted = 0", "WHERE deleted = FALSE", stmt, flags=re.IGNORECASE)
    stmt = re.sub(r"WHERE deleted = 1", "WHERE deleted = TRUE", stmt, flags=re.IGNORECASE)

    if stmt.upper().startswith("INSERT OR IGNORE"):
        stmt = re.sub(r"INSERT OR IGNORE", "INSERT", stmt, flags=re.IGNORECASE, count=1)
        stmt = stmt[:-1] + " ON CONFLICT DO NOTHING;" if stmt.endswith(";") else stmt + " ON CONFLICT DO NOTHING;"

    if not stmt.endswith(";"):
        stmt = stmt + ";"
    return stmt


__all__ = [
    "_convert_sqlite_sql_to_postgres_statements",
    "_transform_sqlite_statement_to_postgres",
]
