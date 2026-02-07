from types import SimpleNamespace

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
import tldw_Server_API.app.core.DB_Management.backends.postgresql_backend as pg_backend


class _DummyConn:
    def __init__(self) -> None:
        self.closed = False
        self.close_calls = 0
        self.row_factory = None

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True


def _configure_fake_psycopg(monkeypatch) -> None:
    def _connect(_dsn: str):
        return _DummyConn()

    monkeypatch.setattr(pg_backend, "PSYCOPG2_AVAILABLE", True, raising=True)
    monkeypatch.setattr(pg_backend, "psycopg_pool", None, raising=False)
    monkeypatch.setattr(pg_backend, "psycopg", SimpleNamespace(connect=_connect), raising=False)
    monkeypatch.setattr(pg_backend, "dict_row", object(), raising=False)


def test_fallback_pool_closes_overflow_connections_on_return(monkeypatch) -> None:
    _configure_fake_psycopg(monkeypatch)
    cfg = DatabaseConfig(backend_type=BackendType.POSTGRESQL, pool_size=1)
    pool = pg_backend.PostgreSQLConnectionPool(cfg)

    managed_conn = pool.get_connection()
    overflow_conn = pool.get_connection()

    assert managed_conn in pool._connections
    assert overflow_conn not in pool._connections

    pool.return_connection(overflow_conn)
    assert overflow_conn.closed is True
    assert overflow_conn not in pool._free

    pool.return_connection(managed_conn)
    assert managed_conn.closed is False
    assert managed_conn in pool._free

    pool.close_all()


def test_fallback_pool_close_all_closes_free_connections(monkeypatch) -> None:
    _configure_fake_psycopg(monkeypatch)
    cfg = DatabaseConfig(backend_type=BackendType.POSTGRESQL, pool_size=1)
    pool = pg_backend.PostgreSQLConnectionPool(cfg)

    conn = pool.get_connection()
    pool.return_connection(conn)
    assert conn in pool._free

    pool.close_all()
    assert conn.closed is True


def test_fallback_pool_close_all_deduplicates_connection_close(monkeypatch) -> None:
    _configure_fake_psycopg(monkeypatch)
    cfg = DatabaseConfig(backend_type=BackendType.POSTGRESQL, pool_size=1)
    pool = pg_backend.PostgreSQLConnectionPool(cfg)

    conn = pool.get_connection()
    # Managed connection is tracked and can also appear in free list.
    pool.return_connection(conn)
    assert conn in pool._connections
    assert conn in pool._free

    pool.close_all()
    assert conn.closed is True
    assert conn.close_calls == 1
