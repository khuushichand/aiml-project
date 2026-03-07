"""Core Text2SQL orchestration service."""

from __future__ import annotations

import time
from typing import Any

from .sql_guard import SqlGuard


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
        out = await self.executor.execute(guarded.sql, timeout_ms=timeout_ms, max_rows=max_rows)

        return {
            "sql": guarded.sql,
            "columns": out["columns"],
            "rows": out["rows"],
            "row_count": out["row_count"],
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "guardrail": {
                "limit_injected": guarded.limit_injected,
                "limit_clamped": guarded.limit_clamped,
            },
            "target_id": target_id,
        }
