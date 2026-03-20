from types import SimpleNamespace

import pytest

import tldw_Server_API.app.core.AuthNZ.database as database_mod
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


class _RecordingAsyncConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.row_factory = None
        self.closed = False
        self.committed = False
        self.rolled_back = False

    async def execute(self, sql: str, *args):
        self.statements.append(sql)
        return _RecordingAsyncCursor(sql)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True


class _RecordingAsyncCursor:
    def __init__(self, sql: str) -> None:
        self.sql = sql

    async def fetchall(self):
        if self.sql.strip().upper() == "PRAGMA DATABASE_LIST":
            return [(0, "main", "")]
        return []


@pytest.mark.asyncio
async def test_sqlite_transaction_uses_begin_immediate(monkeypatch):
    conn = _RecordingAsyncConnection()

    async def _fake_connect(*args, **kwargs):
        return conn

    monkeypatch.setattr(database_mod.aiosqlite, "connect", _fake_connect)

    pool = DatabasePool(settings=SimpleNamespace())
    pool._initialized = True
    pool.pool = None
    pool.db_path = ":memory:"
    pool._sqlite_uri = False

    async with pool.transaction():
        pass

    assert conn.statements[:6] == [
        "PRAGMA database_list",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA foreign_keys=ON",
        "PRAGMA busy_timeout=5000",
        "PRAGMA temp_store=MEMORY",
        "BEGIN IMMEDIATE",
    ]
    assert conn.committed is True
    assert conn.closed is True


@pytest.mark.asyncio
async def test_sqlite_acquire_applies_runtime_pragmas(tmp_path):
    pool = DatabasePool(settings=SimpleNamespace())
    pool._initialized = True
    pool.pool = None
    pool.db_path = str(tmp_path / "users.db")
    pool._sqlite_uri = False

    async with pool.acquire() as conn:
        journal_mode = await (await conn.execute("PRAGMA journal_mode")).fetchone()
        synchronous = await (await conn.execute("PRAGMA synchronous")).fetchone()
        foreign_keys = await (await conn.execute("PRAGMA foreign_keys")).fetchone()
        busy_timeout = await (await conn.execute("PRAGMA busy_timeout")).fetchone()
        temp_store = await (await conn.execute("PRAGMA temp_store")).fetchone()

    assert str(journal_mode[0]).lower() == "wal"
    assert int(synchronous[0]) == 1
    assert int(foreign_keys[0]) == 1
    assert int(busy_timeout[0]) == 5000
    assert int(temp_store[0]) == 2
