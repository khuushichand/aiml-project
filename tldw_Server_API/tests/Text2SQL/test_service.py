import pytest

from tldw_Server_API.app.core.Text2SQL.service import Text2SQLCoreService


class StubGenerator:
    async def generate(self, **kwargs):
        return {"sql": "SELECT id FROM media"}


class StubExecutor:
    async def execute(self, sql: str, *, timeout_ms: int, max_rows: int):
        return {"columns": ["id"], "rows": [[1], [2]], "row_count": 2}


@pytest.mark.asyncio
async def test_service_returns_sql_and_rows() -> None:
    service = Text2SQLCoreService(generator=StubGenerator(), executor=StubExecutor())
    result = await service.generate_and_execute(query="list ids", target_id="media_db")
    assert result["sql"]
    assert result["row_count"] == 2
