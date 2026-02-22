from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.mfa_repo import AuthnzMfaRepo


class _Tx:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ARG002
        return False


class _Acquire:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ARG002
        return False


class _PoolStub:
    def __init__(self, conn: Any, *, postgres: bool) -> None:
        self._conn = conn
        self.pool = object() if postgres else None

    def transaction(self) -> _Tx:
        return _Tx(self._conn)

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


class _Cursor:
    def __init__(self, *, row: Any = None, rowcount: int = 1) -> None:
        self._row = row
        self.rowcount = rowcount

    async def fetchone(self) -> Any:
        return self._row


class _SqliteConnWithPgTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetchrow(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchrow")

    async def fetchval(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchval")

    async def execute(self, query: str, params: Any) -> _Cursor:
        self.execute_calls.append((str(query), params))
        lower_q = str(query).lower()
        if "select totp_secret from users" in lower_q:
            return _Cursor(row=("encrypted-secret",))
        if "select two_factor_enabled" in lower_q:
            return _Cursor(row=(1, 1, 1))
        return _Cursor(rowcount=1)


class _PostgresConnWithSqliteTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchval_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *params: Any) -> str:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.execute_calls.append((str(query), tuple(params)))
        return "UPDATE 1"

    async def fetchrow(self, query: str, *params: Any) -> dict[str, Any]:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.fetchrow_calls.append((str(query), tuple(params)))
        return {
            "two_factor_enabled": True,
            "has_secret": True,
            "has_backup_codes": True,
        }

    async def fetchval(self, query: str, *params: Any) -> str:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.fetchval_calls.append((str(query), tuple(params)))
        return "encrypted-secret"


@pytest.mark.asyncio
async def test_set_mfa_config_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithPgTrap()
    repo = AuthnzMfaRepo(db_pool=_PoolStub(conn, postgres=False))

    await repo.set_mfa_config(
        user_id=7,
        encrypted_secret="enc-secret",
        backup_codes_json='["c1","c2"]',
        updated_at=datetime.now(timezone.utc),
    )

    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "totp_secret = ?" in query
    assert "where id = ?" in query.lower()
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_set_mfa_config_postgres_backend_selection_uses_dollar_params():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzMfaRepo(db_pool=_PoolStub(conn, postgres=True))

    await repo.set_mfa_config(
        user_id=7,
        encrypted_secret="enc-secret",
        backup_codes_json='["c1","c2"]',
        updated_at=datetime.now(timezone.utc),
    )

    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "totp_secret = $1" in query
    assert "where id = $4" in query.lower()
    assert params and params[-1] == 7


@pytest.mark.asyncio
async def test_get_mfa_status_row_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithPgTrap()
    repo = AuthnzMfaRepo(db_pool=_PoolStub(conn, postgres=False))

    row = await repo.get_mfa_status_row(3)

    assert row is not None
    assert row["two_factor_enabled"] == 1
    assert row["has_secret"] == 1
    assert row["has_backup_codes"] == 1
    assert conn.execute_calls
    query, _ = conn.execute_calls[0]
    assert "where id = ?" in query.lower()


@pytest.mark.asyncio
async def test_get_mfa_status_row_postgres_backend_selection_uses_fetchrow():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzMfaRepo(db_pool=_PoolStub(conn, postgres=True))

    row = await repo.get_mfa_status_row(9)

    assert row is not None
    assert row["two_factor_enabled"] is True
    assert conn.fetchrow_calls
    query, params = conn.fetchrow_calls[0]
    assert "where id = $1" in query.lower()
    assert params and params[0] == 9


@pytest.mark.asyncio
async def test_get_encrypted_totp_secret_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithPgTrap()
    repo = AuthnzMfaRepo(db_pool=_PoolStub(conn, postgres=False))

    value = await repo.get_encrypted_totp_secret(4)

    assert value == "encrypted-secret"
    assert conn.execute_calls
    query, _ = conn.execute_calls[0]
    assert "select totp_secret from users where id = ?" in query.lower()


@pytest.mark.asyncio
async def test_get_encrypted_totp_secret_postgres_backend_selection_uses_fetchval():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzMfaRepo(db_pool=_PoolStub(conn, postgres=True))

    value = await repo.get_encrypted_totp_secret(4)

    assert value == "encrypted-secret"
    assert conn.fetchval_calls
    query, params = conn.fetchval_calls[0]
    assert "select totp_secret from users where id = $1" in query.lower()
    assert params and params[0] == 4
