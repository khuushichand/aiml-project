"""Core Text2SQL orchestration service."""

from __future__ import annotations

import time
from typing import Any

from .sql_guard import SqlGuard

MAX_CELL_CHARS = 512
MAX_ROWS = 500


def _normalize_budgeted_row(row: Any) -> tuple[Any, int]:
    """Clamp oversized text cells for a row and return (row, truncated_cells)."""
    truncated_cells = 0

    def _trim(value: Any) -> Any:
        nonlocal truncated_cells
        if isinstance(value, str) and len(value) > MAX_CELL_CHARS:
            truncated_cells += 1
            return value[:MAX_CELL_CHARS]
        return value

    if isinstance(row, dict):
        return ({str(key): _trim(value) for key, value in row.items()}, truncated_cells)
    if isinstance(row, list):
        return ([_trim(value) for value in row], truncated_cells)
    if isinstance(row, tuple):
        return (tuple(_trim(value) for value in row), truncated_cells)
    return (_trim(row), truncated_cells)


def _resolve_max_rows(requested_max_rows: int) -> int:
    try:
        value = int(requested_max_rows)
    except (TypeError, ValueError):
        value = 100
    if value <= 0:
        value = 100
    return min(value, MAX_ROWS)


class Text2SQLCoreService:
    """Generate SQL from NL query, enforce policy, and execute safely."""

    def __init__(self, *, generator: Any, executor: Any, guard: SqlGuard | None = None) -> None:
        self.generator = generator
        self.executor = executor
        self.guard = guard or SqlGuard(default_limit=100, max_limit=500)

    async def generate_and_execute(
        self,
        *,
        query: str,
        target_id: str,
        timeout_ms: int = 5000,
        max_rows: int = 100,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        generated = await self.generator.generate(query=query, target_id=target_id)
        sql = generated.get("sql") if isinstance(generated, dict) else None
        if not isinstance(sql, str) or not sql.strip():
            raise ValueError("SQL generator must return a non-empty 'sql' string")

        guarded = self.guard.validate_and_rewrite(sql)
        applied_max_rows = _resolve_max_rows(max_rows)
        out = await self.executor.execute(guarded.sql, timeout_ms=timeout_ms, max_rows=applied_max_rows)

        raw_rows = out.get("rows", [])
        if not isinstance(raw_rows, list):
            raw_rows = []
        rows_before_budget = len(raw_rows)
        rows_truncated = rows_before_budget > applied_max_rows
        bounded_rows = raw_rows[:applied_max_rows]

        budgeted_rows: list[Any] = []
        cells_truncated = 0
        for row in bounded_rows:
            normalized_row, truncated_count = _normalize_budgeted_row(row)
            cells_truncated += int(truncated_count)
            budgeted_rows.append(normalized_row)

        pre_truncated = bool(out.get("truncated", False))
        any_budget_truncation = rows_truncated or cells_truncated > 0

        return {
            "sql": guarded.sql,
            "columns": out["columns"],
            "rows": budgeted_rows,
            "row_count": len(budgeted_rows),
            "row_count_total": rows_before_budget,
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "guardrail": {
                "limit_injected": guarded.limit_injected,
                "limit_clamped": guarded.limit_clamped,
                "result_budget": {
                    "applied_max_rows": applied_max_rows,
                    "max_cell_chars": MAX_CELL_CHARS,
                    "rows_truncated": rows_truncated,
                    "cells_truncated": cells_truncated,
                },
            },
            "truncated": bool(pre_truncated or any_budget_truncation),
            "target_id": target_id,
        }
