import sqlite3

import pytest

from tldw_Server_API.app.core.Text2SQL.executor import SqliteReadOnlyExecutor


@pytest.mark.asyncio
async def test_sqlite_executor_enforces_read_only(tmp_path) -> None:
    db = tmp_path / "ro.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO items(name) VALUES('ok')")
    conn.commit()
    conn.close()

    executor = SqliteReadOnlyExecutor(str(db))
    out = await executor.execute("SELECT id, name FROM items", timeout_ms=2000, max_rows=50)
    assert out["row_count"] == 1

    with pytest.raises(Exception):
        await executor.execute("DELETE FROM items", timeout_ms=2000, max_rows=50)
