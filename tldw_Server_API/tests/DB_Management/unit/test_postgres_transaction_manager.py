import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import (
    BackendType,
    DatabaseConfig,
)
from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import (
    PostgreSQLBackend,
)


class DummyConn:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _pg_backend():
    # Construct without touching real pool/psycopg; tests pass a connection explicitly
    return PostgreSQLBackend(DatabaseConfig(backend_type=BackendType.POSTGRESQL))


def test_transaction_outermost_commits_with_external_connection():
    backend = _pg_backend()
    conn = DummyConn()

    # Single outermost transaction should commit exactly once
    with backend.transaction(connection=conn):
        pass

    assert conn.commits == 1
    assert conn.rollbacks == 0


def test_transaction_nested_commits_once_with_external_connection():
    backend = _pg_backend()
    conn = DummyConn()

    # Nested transactions on same connection should only commit at outermost
    with backend.transaction(connection=conn):
        with backend.transaction(connection=conn):
            pass

    assert conn.commits == 1
    assert conn.rollbacks == 0


def test_transaction_rollback_on_exception_with_external_connection():
    backend = _pg_backend()
    conn = DummyConn()

    with pytest.raises(RuntimeError):
        with backend.transaction(connection=conn):
            raise RuntimeError("boom")

    assert conn.commits == 0
    assert conn.rollbacks == 1


def test_transaction_nested_rollback_only_once_on_exception_with_external_connection():
    backend = _pg_backend()
    conn = DummyConn()

    with pytest.raises(ValueError):
        with backend.transaction(connection=conn):
            with backend.transaction(connection=conn):
                raise ValueError("fail nested")

    # Only outermost rollback should occur
    assert conn.commits == 0
    assert conn.rollbacks == 1
