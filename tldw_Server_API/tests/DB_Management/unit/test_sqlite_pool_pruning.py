import threading

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.sqlite_backend import SQLiteConnectionPool


def test_sqlite_pool_prunes_dead_threads(tmp_path):
    db_path = tmp_path / "pool_test.db"
    config = DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=str(db_path))
    pool = SQLiteConnectionPool(str(db_path), config)

    def worker():
        conn = pool.get_connection()
        conn.execute("SELECT 1")

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    pool.get_connection()
    stats = pool.get_stats()
    assert stats["total_connections"] == 1
    pool.close_all()
