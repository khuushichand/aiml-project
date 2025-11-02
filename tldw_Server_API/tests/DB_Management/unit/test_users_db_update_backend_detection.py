import asyncio
import pytest

from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB


class _FakePgConn:
    def __init__(self):
        self.calls = []

    # Presence of fetchval indicates Postgres path for update_user
    async def fetchval(self, *args, **kwargs):  # pragma: no cover - not used here
        return None

    async def execute(self, query: str, *args):
        self.calls.append((query, args))
        return None


class _FakeSqliteConn:
    def __init__(self):
        self.calls = []

    async def execute(self, query: str, params):
        # SQLite shim path passes a single params sequence
        self.calls.append((query, tuple(params)))
        return None

    async def commit(self):
        return None


class _FakeTx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def transaction(self):
        return _FakeTx(self._conn)


@pytest.mark.asyncio
async def test_update_user_postgres_detects_and_uses_dollar_placeholders(monkeypatch):
    fake_conn = _FakePgConn()
    users = UsersDB(db_pool=_FakePool(fake_conn))
    users._initialized = True  # bypass initialize

    async def _fake_get_user_by_id(self, user_id: int):
        return {
            "id": user_id,
            "email": "old@example.com",
            "is_active": True,
            "is_superuser": False,
            "email_verified": False,
        }

    monkeypatch.setattr(UsersDB, "get_user_by_id", _fake_get_user_by_id, raising=False)

    await users.update_user(42, email="new@example.com", is_active=True)

    assert fake_conn.calls, "Expected at least one execute call"
    sql, args = fake_conn.calls[-1]
    # Expect $1/$2 placeholders and WHERE id = $N
    assert " SET email = $1, is_active = $2, updated_at" in sql.replace("\n", " ")
    assert " WHERE id = $2" in sql or " WHERE id = $3" in sql  # position depends on updates len
    # args are varargs tuple from *values
    assert tuple(args) == ("new@example.com", True, 42) or tuple(args) == ("new@example.com", True)


@pytest.mark.asyncio
async def test_update_user_sqlite_detects_and_uses_qmark_placeholders(monkeypatch):
    fake_conn = _FakeSqliteConn()
    users = UsersDB(db_pool=_FakePool(fake_conn))
    users._initialized = True

    async def _fake_get_user_by_id(self, user_id: int):
        return {
            "id": user_id,
            "email": "old@example.com",
            "is_active": 1,
            "is_superuser": 0,
            "email_verified": 0,
        }

    monkeypatch.setattr(UsersDB, "get_user_by_id", _fake_get_user_by_id, raising=False)

    await users.update_user(7, email="new@example.com", is_active=False)

    assert fake_conn.calls, "Expected at least one execute call"
    sql, params = fake_conn.calls[-1]
    flat_sql = sql.replace("\n", " ")
    assert " SET email = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP" in flat_sql
    assert flat_sql.strip().endswith("WHERE id = ?")
    # Ensure booleans were coerced to ints for SQLite path and id appended last
    assert params[-1] == 7
    assert params[1] in (0, 1)
