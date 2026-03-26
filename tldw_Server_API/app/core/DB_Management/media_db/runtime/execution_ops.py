"""Query execution helpers for the package-native Media DB runtime."""

from __future__ import annotations

from contextlib import suppress
from loguru import logger as logging
import sqlite3
from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseError as BackendDatabaseError,
    QueryResult,
)
from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError
from tldw_Server_API.app.core.DB_Management.media_db.runtime.execution import (
    close_sqlite_ephemeral,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.rows import (
    BackendCursorAdapter,
)

_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def _execute_with_connection(
    self: Any,
    conn,
    query: str,
    params: tuple | list | dict | None = None,
):
    prepared_query, prepared_params = self._prepare_backend_statement(query, params)

    if self.backend_type == BackendType.SQLITE:
        cursor = conn.cursor()
        cursor.execute(prepared_query, prepared_params or ())
        return cursor

    try:
        result = self.backend.execute(
            prepared_query,
            prepared_params,
            connection=conn,
        )
        return BackendCursorAdapter(result)
    except BackendDatabaseError as exc:
        logging.error(
            "Backend execute failed: {}... Error: {}",
            prepared_query[:200],
            exc,
            exc_info=True,
        )
        raise DatabaseError(f"Backend execute failed: {exc}") from exc  # noqa: TRY003


def _executemany_with_connection(
    self: Any,
    conn,
    query: str,
    params_list: list[tuple | list | dict],
):
    prepared_query, prepared_params_list = self._prepare_backend_many_statement(query, params_list)

    if self.backend_type == BackendType.SQLITE:
        cursor = conn.cursor()
        cursor.executemany(prepared_query, prepared_params_list)
        return cursor

    try:
        result = self.backend.execute_many(
            prepared_query,
            prepared_params_list,
            connection=conn,
        )
        return BackendCursorAdapter(result)
    except BackendDatabaseError as exc:
        logging.error(
            "Backend execute_many failed: {}... Error: {}",
            prepared_query[:200],
            exc,
            exc_info=True,
        )
        raise DatabaseError(f"Backend execute_many failed: {exc}") from exc  # noqa: TRY003


def _fetchone_with_connection(
    self: Any,
    conn,
    query: str,
    params: tuple | list | dict | None = None,
) -> dict[str, Any] | None:
    cursor = self._execute_with_connection(conn, query, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(row)


def _fetchall_with_connection(
    self: Any,
    conn,
    query: str,
    params: tuple | list | dict | None = None,
) -> list[dict[str, Any]]:
    cursor = self._execute_with_connection(conn, query, params)
    rows = cursor.fetchall() or []
    return [dict(r) for r in rows]


def execute_query(
    self: Any,
    query: str,
    params: tuple | list | dict | None = None,
    *,
    commit: bool = False,
    connection: Any | None = None,
):
    """
    Executes a single SQL query.

    This mirrors the legacy Media_DB_v2 control flow exactly, including:
    - ephemeral SQLite cleanup semantics,
    - sync-trigger IntegrityError passthrough,
    - backend error translation, and
    - the existing query-result adapter contract.
    """
    prepared_query, prepared_params = self._prepare_backend_statement(query, params)

    eff_conn = connection or self._get_txn_conn()

    if self.backend_type == BackendType.SQLITE:
        try:
            if eff_conn is None and not self.is_memory_db:
                eph = sqlite3.connect(self.db_path_str, check_same_thread=False)
                cur = None
                try:
                    eph.row_factory = sqlite3.Row
                    self._apply_sqlite_connection_pragmas(eph)
                    cur = eph.cursor()
                    cur.execute(prepared_query, prepared_params or ())
                    upper = prepared_query.strip().upper()
                    is_select = upper.startswith("SELECT")
                    has_returning = " RETURNING " in upper
                    rows = []
                    if is_select or has_returning:
                        rows = [dict(r) for r in cur.fetchall()]
                    if commit or not is_select:
                        with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                            eph.commit()
                    result = QueryResult(
                        rows=rows,
                        rowcount=cur.rowcount,
                        lastrowid=cur.lastrowid,
                        description=cur.description,
                    )
                    return BackendCursorAdapter(result)
                finally:
                    close_sqlite_ephemeral(cur, eph)
            else:
                conn_use = eff_conn or self.get_connection()
                cur = conn_use.cursor()
                cur.execute(prepared_query, prepared_params or ())
                if commit and conn_use:
                    conn_use.commit()
                upper = prepared_query.strip().upper()
                is_select = upper.startswith("SELECT")
                has_returning = " RETURNING " in upper
                rows = []
                if is_select or has_returning:
                    rows = [dict(r) for r in cur.fetchall()]
                result = QueryResult(
                    rows=rows,
                    rowcount=cur.rowcount,
                    lastrowid=cur.lastrowid,
                    description=cur.description,
                )
                return BackendCursorAdapter(result)
        except sqlite3.IntegrityError as exc:
            msg = str(exc).lower()
            if "sync error" in msg:
                logging.exception("Sync Validation Failed")
                raise
            logging.error("Integrity error executing query: {}", exc, exc_info=True)
            raise DatabaseError(f"Integrity constraint violation: {exc}") from exc  # noqa: TRY003
        except sqlite3.Error as exc:
            logging.error("SQLite query failed: {}", exc, exc_info=True)
            raise DatabaseError(f"Query execution failed: {exc}") from exc  # noqa: TRY003

    try:
        if eff_conn is None:
            result = self.backend.execute(prepared_query, prepared_params)
        else:
            result = self.backend.execute(prepared_query, prepared_params, connection=eff_conn)
            if commit:
                try:
                    eff_conn.commit()
                except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
                    raise DatabaseError(f"Backend commit failed: {exc}") from exc  # noqa: TRY003
        return BackendCursorAdapter(result)
    except BackendDatabaseError as exc:
        logging.error("Backend query failed: {}", exc, exc_info=True)
        raise DatabaseError(f"Backend query execution failed: {exc}") from exc  # noqa: TRY003


def execute_many(
    self: Any,
    query: str,
    params_list: list[tuple | list | dict],
    *,
    commit: bool = False,
    connection: Any | None = None,
) -> object | None:
    """
    Executes a SQL query for multiple sets of parameters.
    """
    if not isinstance(params_list, list):
        raise TypeError("params_list must be a list of parameter iterables for execute_many().")  # noqa: TRY003
    if not params_list:
        logging.debug("execute_many received empty params_list; nothing to execute.")
        return None

    prepared_query, prepared_params_list = self._prepare_backend_many_statement(query, params_list)

    eff_conn = connection or self._get_txn_conn()

    if self.backend_type == BackendType.SQLITE:
        try:
            if eff_conn is None and not self.is_memory_db:
                eph = sqlite3.connect(self.db_path_str, check_same_thread=False)
                cur = None
                try:
                    eph.row_factory = sqlite3.Row
                    self._apply_sqlite_connection_pragmas(eph)
                    cur = eph.cursor()
                    cur.executemany(prepared_query, prepared_params_list)
                    with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                        eph.commit()
                    result = QueryResult(
                        rows=[],
                        rowcount=cur.rowcount,
                        lastrowid=cur.lastrowid,
                        description=cur.description,
                    )
                    return BackendCursorAdapter(result)
                finally:
                    close_sqlite_ephemeral(cur, eph)
            else:
                conn_use = eff_conn or self.get_connection()
                cur = conn_use.cursor()
                cur.executemany(prepared_query, prepared_params_list)
                if commit and conn_use:
                    conn_use.commit()
                result = QueryResult(
                    rows=[],
                    rowcount=cur.rowcount,
                    lastrowid=cur.lastrowid,
                    description=cur.description,
                )
                return BackendCursorAdapter(result)
        except sqlite3.IntegrityError as exc:
            logging.error("Integrity error during execute_many: {}", exc, exc_info=True)
            raise DatabaseError(f"Integrity constraint violation during batch: {exc}") from exc  # noqa: TRY003
        except sqlite3.Error as exc:
            logging.error("SQLite execute_many failed: {}", exc, exc_info=True)
            raise DatabaseError(f"Execute Many failed: {exc}") from exc  # noqa: TRY003
        except TypeError as te:
            logging.error("TypeError during execute_many: {}", te, exc_info=True)
            raise TypeError(f"Parameter list format error: {te}") from te  # noqa: TRY003

    try:
        if eff_conn is None:
            result = self.backend.execute_many(prepared_query, prepared_params_list)
        else:
            result = self.backend.execute_many(
                prepared_query,
                prepared_params_list,
                connection=eff_conn,
            )
            if commit:
                try:
                    eff_conn.commit()
                except _MEDIA_NONCRITICAL_EXCEPTIONS as exc:
                    raise DatabaseError(f"Backend batch commit failed: {exc}") from exc  # noqa: TRY003
        return BackendCursorAdapter(result)
    except BackendDatabaseError as exc:
        logging.error("Backend execute_many failed: {}", exc, exc_info=True)
        raise DatabaseError(f"Backend execute_many failed: {exc}") from exc  # noqa: TRY003


__all__ = [
    "_execute_with_connection",
    "_executemany_with_connection",
    "_fetchall_with_connection",
    "_fetchone_with_connection",
    "execute_many",
    "execute_query",
]
