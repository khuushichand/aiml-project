"""Package-owned claims FTS rebuild helper."""

from __future__ import annotations

import logging
import sqlite3

from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseError as BackendDatabaseError,
)
from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError


def rebuild_claims_fts(self) -> int:
    """
    Rebuild the claims full-text search index using the active backend.

    Returns:
        int: Number of rows indexed.
    """
    try:
        with self.transaction() as conn:
            if self.backend_type == BackendType.SQLITE:
                try:
                    self._execute_with_connection(
                        conn,
                        "INSERT INTO claims_fts(claims_fts) VALUES ('delete-all')",
                    )
                except sqlite3.Error as sqlite_err:
                    logging.warning(
                        "claims_fts table missing during rebuild; recreating. Error: %s",
                        sqlite_err,
                    )
                    self._execute_with_connection(
                        conn,
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
                            claim_text,
                            content='Claims',
                            content_rowid='id'
                        )
                        """,
                    )
                    self._execute_with_connection(
                        conn,
                        "INSERT INTO claims_fts(claims_fts) VALUES ('delete-all')",
                    )
                self._execute_with_connection(
                    conn,
                    "INSERT INTO claims_fts(rowid, claim_text) SELECT id, claim_text FROM Claims WHERE deleted = 0",
                )
                count_row = self._fetchone_with_connection(
                    conn,
                    "SELECT COUNT(*) AS total FROM claims_fts",
                )
                return int(count_row.get("total", 0)) if count_row else 0
            if self.backend_type == BackendType.POSTGRESQL:
                backend = self.backend
                backend.create_fts_table(
                    table_name="claims_fts",
                    source_table="claims",
                    columns=["claim_text"],
                    connection=conn,
                )
                rebuild_query = (
                    "UPDATE claims "
                    "SET claims_fts_tsv = CASE "
                    "WHEN deleted = 0 THEN to_tsvector('english', coalesce(claim_text, '')) "
                    "ELSE NULL END"
                )
                self._execute_with_connection(conn, rebuild_query)
                count_row = self._fetchone_with_connection(
                    conn,
                    "SELECT COUNT(*) AS total FROM claims WHERE deleted = 0",
                )
                return int(count_row.get("total", 0)) if count_row else 0
            raise NotImplementedError(
                f"Claims FTS rebuild not implemented for backend {self.backend_type}"
            )
    except sqlite3.Error as exc:
        logging.error(f"Failed to rebuild claims_fts: {exc}", exc_info=True)
        raise DatabaseError(f"Failed to rebuild claims_fts: {exc}") from exc  # noqa: TRY003
    except BackendDatabaseError as exc:
        logging.error(f"Failed to rebuild claims_fts (backend): {exc}", exc_info=True)
        raise DatabaseError(f"Failed to rebuild claims_fts: {exc}") from exc  # noqa: TRY003
