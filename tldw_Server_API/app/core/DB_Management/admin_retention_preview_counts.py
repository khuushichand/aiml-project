from __future__ import annotations

from datetime import datetime
from typing import Any

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool


async def count_retention_window(
    *,
    table: str,
    column: str,
    older_than: datetime | str,
    not_older_than: datetime | str,
    is_date_column: bool = False,
) -> int:
    """Count rows in one retention window for a known table/column pair."""
    db_pool = await get_db_pool()
    is_postgres = bool(getattr(db_pool, "pool", None))

    if isinstance(older_than, datetime):
        older_than_param: Any = older_than.replace(tzinfo=None) if is_postgres else older_than.isoformat()
    else:
        older_than_param = older_than
    if isinstance(not_older_than, datetime):
        not_older_than_param: Any = (
            not_older_than.replace(tzinfo=None) if is_postgres else not_older_than.isoformat()
        )
    else:
        not_older_than_param = not_older_than

    if is_postgres:
        cast = "::date" if is_date_column else ""
        query = (
            f"SELECT COUNT(*) FROM {table} "  # nosec B608
            f"WHERE {column}{cast} < $1 AND {column}{cast} >= $2"  # nosec B608
        )
        total = await db_pool.fetchval(query, older_than_param, not_older_than_param)
    elif is_date_column:
        query = (
            f"SELECT COUNT(*) FROM {table} "  # nosec B608
            f"WHERE DATE({column}) < DATE(?) AND DATE({column}) >= DATE(?)"  # nosec B608
        )
        total = await db_pool.fetchval(query, older_than_param, not_older_than_param)
    else:
        query = (
            f"SELECT COUNT(*) FROM {table} "  # nosec B608
            f"WHERE datetime({column}) < datetime(?) AND datetime({column}) >= datetime(?)"  # nosec B608
        )
        total = await db_pool.fetchval(query, older_than_param, not_older_than_param)
    return int(total or 0)
