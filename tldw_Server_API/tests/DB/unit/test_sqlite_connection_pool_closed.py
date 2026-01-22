import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig, DatabaseError
from tldw_Server_API.app.core.DB_Management.backends.sqlite_backend import SQLiteConnectionPool


def test_sqlite_connection_pool_rejects_after_close() -> None:
    config = DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=":memory:")
    pool = SQLiteConnectionPool(config.sqlite_path or ":memory:", config)

    conn = pool.get_connection()
    assert conn is not None

    pool.close_all()
    with pytest.raises(DatabaseError):
        pool.get_connection()
