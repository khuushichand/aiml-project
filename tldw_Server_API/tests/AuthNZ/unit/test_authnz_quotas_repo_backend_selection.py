from __future__ import annotations

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.quotas_repo import AuthnzQuotasRepo


class _Tx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _PoolStub:
    def __init__(self, conn, *, postgres: bool):
        self._conn = conn
        self.pool = object() if postgres else None

    def transaction(self):
        return _Tx(self._conn)


class _CursorStub:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _SQLiteConnWithFetchvalTrap:
    """
    SQLite-like connection shim that intentionally exposes ``fetchval``.

    The repo must still choose SQLite SQL when db_pool.pool is None.
    """

    def __init__(self):
        self.jwt_count = 0
        self.api_key_count = 0

    async def execute(self, query, params):  # noqa: ANN001
        q = str(query).lower()
        if "update vk_jwt_counters" in q:
            self.jwt_count += 1
            return _CursorStub(None)
        if "update vk_api_key_counters" in q:
            self.api_key_count += 1
            return _CursorStub(None)
        if "select count from vk_jwt_counters" in q:
            return _CursorStub((self.jwt_count,))
        if "select count from vk_api_key_counters" in q:
            return _CursorStub((self.api_key_count,))
        return _CursorStub(None)

    async def fetchval(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchval")


class _PostgresConnStub:
    def __init__(self):
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._count = 0

    async def fetchval(self, query, *params):  # noqa: ANN001
        self.calls.append((str(query), tuple(params)))
        self._count += 1
        return self._count

    async def execute(self, query, params):  # noqa: ANN001, ARG002
        raise AssertionError(f"Postgres backend path should not call conn.execute: {query!r}")


@pytest.mark.asyncio
async def test_sqlite_backend_selection_uses_sqlite_path_even_if_conn_has_fetchval():
    conn = _SQLiteConnWithFetchvalTrap()
    repo = AuthnzQuotasRepo(db_pool=_PoolStub(conn, postgres=False))

    allowed1, count1 = await repo.increment_and_check_jwt_quota(
        jti="jwt-sqlite-backend",
        counter_type="test",
        limit=1,
    )
    allowed2, count2 = await repo.increment_and_check_jwt_quota(
        jti="jwt-sqlite-backend",
        counter_type="test",
        limit=1,
    )

    assert allowed1 is True and count1 == 1
    assert allowed2 is False and count2 == 2


@pytest.mark.asyncio
async def test_postgres_backend_selection_uses_fetchval_path():
    conn = _PostgresConnStub()
    repo = AuthnzQuotasRepo(db_pool=_PoolStub(conn, postgres=True))

    allowed1, count1 = await repo.increment_and_check_api_key_quota(
        api_key_id=42,
        counter_type="audio",
        bucket="unit",
        limit=1,
    )
    allowed2, count2 = await repo.increment_and_check_api_key_quota(
        api_key_id=42,
        counter_type="audio",
        bucket="unit",
        limit=1,
    )

    assert allowed1 is True and count1 == 1
    assert allowed2 is False and count2 == 2
    assert conn.calls, "expected Postgres fetchval path to be used"
    assert "insert into vk_api_key_counters" in conn.calls[0][0].lower()

