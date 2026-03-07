"""Execution interfaces for Text2SQL backends."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import aiosqlite


class SqlExecutor(Protocol):
    """Async SQL executor contract used by Text2SQL service orchestration."""

    async def execute(self, sql: str, *, timeout_ms: int, max_rows: int) -> dict[str, Any]:
        """Execute SQL and return structured rows."""


class SqliteReadOnlyExecutor:
    """Reference read-only executor used in tests and local internal targets."""

    def __init__(self, db_path: str) -> None:
        self._db_path = str(Path(db_path))

    def _readonly_uri(self) -> str:
        absolute_path = Path(self._db_path).resolve()
        return f"file:{quote(str(absolute_path))}?mode=ro"

    async def execute(self, sql: str, *, timeout_ms: int, max_rows: int) -> dict[str, Any]:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if max_rows <= 0:
            raise ValueError("max_rows must be positive")

        async def _run() -> dict[str, Any]:
            async with aiosqlite.connect(self._readonly_uri(), uri=True) as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute("PRAGMA query_only = ON")
                cursor = await conn.execute(sql)
                description = cursor.description
                if description is None:
                    return {"columns": [], "rows": [], "row_count": 0, "truncated": False}

                rows = await cursor.fetchmany(max_rows + 1)
                truncated = len(rows) > max_rows
                bounded_rows = rows[:max_rows]
                columns = [column[0] for column in description]
                return {
                    "columns": columns,
                    "rows": [dict(row) for row in bounded_rows],
                    "row_count": len(bounded_rows),
                    "truncated": truncated,
                }

        timeout_seconds = timeout_ms / 1000.0
        return await asyncio.wait_for(_run(), timeout=timeout_seconds)
