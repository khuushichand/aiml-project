from __future__ import annotations

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.sessions_repo import AuthnzSessionsRepo


class _AcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, conn, *, postgres: bool):
        self._conn = conn
        self.pool = object() if postgres else None

    def acquire(self):
        return _AcquireCtx(self._conn)


class _PostgresConn:
    def __init__(self):
        self.queries: list[str] = []
        self.candidates: list[str] = []

    async def fetchrow(self, query: str, candidate: str):
        self.queries.append(query)
        self.candidates.append(candidate)
        if candidate == "hash-refresh-valid":
            return {
                "id": 11,
                "user_id": 7,
                "token_hash": "hash-access-valid",
                "refresh_token_hash": "hash-refresh-valid",
            }
        return None


class _SqliteCursor:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _SqliteConn:
    def __init__(self):
        self.queries: list[str] = []
        self.candidates: list[str] = []

    async def execute(self, query: str, params):
        self.queries.append(query)
        candidate = params[0]
        self.candidates.append(candidate)
        if candidate == "hash-refresh-valid":
            return _SqliteCursor((22, 8, "hash-access-valid", "hash-refresh-valid"))
        return _SqliteCursor(None)


@pytest.mark.asyncio
async def test_refresh_lookup_postgres_query_includes_refresh_expiry_gate():
    conn = _PostgresConn()
    repo = AuthnzSessionsRepo(_Pool(conn, postgres=True))

    found = await repo.find_active_session_by_refresh_hash_candidates(
        ["hash-refresh-expired", "hash-refresh-valid"]
    )

    assert found == {
        "id": 11,
        "user_id": 7,
        "token_hash": "hash-access-valid",
        "refresh_token_hash": "hash-refresh-valid",
    }
    assert conn.candidates == ["hash-refresh-expired", "hash-refresh-valid"]
    assert conn.queries
    assert all("refresh_expires_at IS NOT NULL" in query for query in conn.queries)
    assert all("refresh_expires_at > CURRENT_TIMESTAMP" in query for query in conn.queries)


@pytest.mark.asyncio
async def test_refresh_lookup_sqlite_query_includes_refresh_expiry_gate():
    conn = _SqliteConn()
    repo = AuthnzSessionsRepo(_Pool(conn, postgres=False))

    found = await repo.find_active_session_by_refresh_hash_candidates(
        ["hash-refresh-expired", "hash-refresh-valid"]
    )

    assert found == {
        "id": 22,
        "user_id": 8,
        "token_hash": "hash-access-valid",
        "refresh_token_hash": "hash-refresh-valid",
    }
    assert conn.candidates == ["hash-refresh-expired", "hash-refresh-valid"]
    assert conn.queries
    assert all("refresh_expires_at IS NOT NULL" in query for query in conn.queries)
    assert all("datetime(refresh_expires_at) > datetime('now')" in query for query in conn.queries)
