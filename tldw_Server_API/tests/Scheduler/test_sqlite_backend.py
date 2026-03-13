from pathlib import Path

import pytest

from tldw_Server_API.app.core.Scheduler.backends.sqlite_backend import SQLiteBackend
from tldw_Server_API.app.core.Scheduler.config import SchedulerConfig


@pytest.mark.asyncio
async def test_sqlite_backend_enables_foreign_keys_on_all_connections(tmp_path: Path):
    db_path = tmp_path / "scheduler.db"
    config = SchedulerConfig(
        database_url=f"sqlite:///{db_path}",
        base_path=tmp_path / "scheduler-data",
    )
    config.sqlite_pool_size = 2

    backend = SQLiteBackend(config)
    await backend.connect()

    try:
        for conn in [backend._connection, backend._write_conn, *backend._read_pool]:
            cursor = await conn.execute("PRAGMA foreign_keys")
            row = await cursor.fetchone()
            assert row[0] == 1
    finally:
        await backend.disconnect()


@pytest.mark.asyncio
async def test_sqlite_backend_transaction_uses_begin_immediate():
    class _RecordingAsyncConnection:
        def __init__(self) -> None:
            self.statements: list[str] = []
            self.committed = False
            self.rolled_back = False

        async def execute(self, sql: str, *args):
            self.statements.append(sql)
            return None

        async def commit(self) -> None:
            self.committed = True

        async def rollback(self) -> None:
            self.rolled_back = True

    backend = SQLiteBackend.__new__(SQLiteBackend)
    backend._lock = __import__("asyncio").Lock()
    backend._connection = _RecordingAsyncConnection()

    async with backend.transaction():
        pass

    assert backend._connection.statements == ["BEGIN IMMEDIATE"]
    assert backend._connection.committed is True
