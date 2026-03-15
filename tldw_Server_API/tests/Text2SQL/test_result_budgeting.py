import pytest

from tldw_Server_API.app.core.Text2SQL.service import Text2SQLCoreService


class _StubGenerator:
    async def generate(self, **kwargs):
        _ = kwargs
        return {"sql": "SELECT id, body FROM media"}


class _OverproducingExecutor:
    async def execute(self, sql: str, *, timeout_ms: int, max_rows: int):
        _ = sql
        _ = timeout_ms
        _ = max_rows
        rows = [{"id": i, "body": "x" * 700} for i in range(600)]
        return {
            "columns": ["id", "body"],
            "rows": rows,
            "row_count": len(rows),
            "truncated": False,
        }


class _IgnoringMaxRowsExecutor:
    async def execute(self, sql: str, *, timeout_ms: int, max_rows: int):
        _ = sql
        _ = timeout_ms
        _ = max_rows
        rows = [{"id": i, "body": "ok"} for i in range(25)]
        return {
            "columns": ["id", "body"],
            "rows": rows,
            "row_count": len(rows),
            "truncated": False,
        }


@pytest.mark.asyncio
async def test_sql_rows_are_truncated_when_budget_exceeded():
    service = Text2SQLCoreService(generator=_StubGenerator(), executor=_OverproducingExecutor())

    result = await service.generate_and_execute(
        query="show rows",
        target_id="media_db",
        max_rows=1000,
    )

    assert len(result["rows"]) == 500
    assert result["row_count"] == 500
    assert result["truncated"] is True
    assert result["guardrail"]["result_budget"]["rows_truncated"] is True
    assert result["guardrail"]["result_budget"]["cells_truncated"] > 0
    assert all(len(row["body"]) <= 512 for row in result["rows"])


@pytest.mark.asyncio
async def test_service_enforces_requested_max_rows_even_if_executor_overproduces():
    service = Text2SQLCoreService(generator=_StubGenerator(), executor=_IgnoringMaxRowsExecutor())

    result = await service.generate_and_execute(
        query="show rows",
        target_id="media_db",
        max_rows=7,
    )

    assert len(result["rows"]) == 7
    assert result["row_count"] == 7
    assert result["truncated"] is True
    assert result["guardrail"]["result_budget"]["applied_max_rows"] == 7
