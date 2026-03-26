"""Package-owned internal data-table helpers for the Media DB runtime."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope

_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def _resolve_data_tables_owner(self: Any, owner_user_id: int | str | None) -> str | None:
    """Resolve the owner user id for data table queries."""
    if owner_user_id is not None:
        return str(owner_user_id)
    try:
        scope = get_scope()
    except _MEDIA_NONCRITICAL_EXCEPTIONS:
        logger.debug("Failed to resolve scope for data tables owner")
        return None
    if scope and not scope.is_admin and scope.user_id is not None:
        return str(scope.user_id)
    return None


def _resolve_data_table_write_client_id(
    self: Any,
    table_id: int,
    *,
    owner_user_id: int | str | None = None,
) -> str:
    """Resolve the client_id that should own table child writes."""
    owner_filter = self._resolve_data_tables_owner(owner_user_id)
    if owner_filter is not None and owner_filter.strip():
        return owner_filter.strip()

    row = self.execute_query(
        "SELECT client_id FROM data_tables WHERE id = ? LIMIT 1",
        (int(table_id),),
    ).fetchone()
    if not row:
        raise InputError("data_table_not_found")
    client_id = str(row.get("client_id") if isinstance(row, dict) else row[0] if row else "").strip()
    if not client_id:
        raise InputError("data_table_owner_missing")
    return client_id


def _get_data_table_owner_client_id(self: Any, conn: Any, table_id: int) -> str | None:
    """Fetch the owning client_id for a data table id."""
    row = self._fetchone_with_connection(
        conn,
        "SELECT client_id FROM data_tables WHERE id = ? AND deleted = 0",
        (int(table_id),),
    )
    if not row:
        return None
    return str(row.get("client_id"))


def _soft_delete_data_table_children(
    self: Any,
    conn: Any,
    table_id: int,
    now: str,
    *,
    owner_user_id: int | None = None,
) -> None:
    """Soft delete data table child records within a transaction."""
    owner_filter = self._resolve_data_tables_owner(owner_user_id)
    where_clause = "WHERE table_id = ? AND deleted = 0"
    params: list[Any] = [now, int(table_id)]
    if owner_filter is not None:
        where_clause += " AND client_id = ?"
        params.append(owner_filter)
    for table in ("data_table_columns", "data_table_rows", "data_table_sources"):
        self._execute_with_connection(
            conn,
            """
            UPDATE {table}
            SET deleted = 1,
                last_modified = ?,
                version = version + 1
            {where_clause}
            """.format_map(locals()),  # nosec B608
            tuple(params),
        )


def _normalize_data_table_row_json(
    self: Any,
    row_json: Any,
    *,
    column_ids: set[str] | None = None,
    validate_keys: bool = True,
) -> str:
    """Normalize row_json to a JSON string and validate column keys."""
    del self

    if row_json is None:
        raise InputError("row_json is required for data table rows")  # noqa: TRY003
    payload = row_json
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise InputError(f"row_json must be valid JSON: {exc}") from exc  # noqa: TRY003

    if validate_keys:
        if column_ids is None:
            raise InputError("column_ids are required for row_json validation")  # noqa: TRY003
        if not isinstance(payload, dict):
            raise InputError("row_json must be an object keyed by column_id")  # noqa: TRY003
        normalized: dict[str, Any] = {str(key): value for key, value in payload.items()}
        invalid = [key for key in normalized if key not in column_ids]
        if invalid:
            raise InputError(f"row_json contains unknown column_id(s): {', '.join(invalid)}")  # noqa: TRY003
        payload = normalized

    if not isinstance(payload, (dict, list)):
        raise InputError("row_json must be an object or array")  # noqa: TRY003
    return json.dumps(payload)
