from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.sqlite_backend import SQLiteBackend


def test_sqlite_fts_triggers_keep_index_in_sync():
    config = DatabaseConfig(backend_type=BackendType.SQLITE, sqlite_path=":memory:")
    backend = SQLiteBackend(config)
    conn = backend.connect()
    try:
        conn.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, title TEXT)")
        backend.create_fts_table("items_fts", "items", ["title"], connection=conn)

        conn.execute("INSERT INTO items(title) VALUES ('alpha')")
        rows = conn.execute("SELECT rowid FROM items_fts WHERE items_fts MATCH 'alpha'").fetchall()
        assert len(rows) == 1

        conn.execute("UPDATE items SET title='beta' WHERE id=1")
        rows = conn.execute("SELECT rowid FROM items_fts WHERE items_fts MATCH 'beta'").fetchall()
        assert len(rows) == 1
        rows = conn.execute("SELECT rowid FROM items_fts WHERE items_fts MATCH 'alpha'").fetchall()
        assert len(rows) == 0

        conn.execute("DELETE FROM items WHERE id=1")
        rows = conn.execute("SELECT rowid FROM items_fts WHERE items_fts MATCH 'beta'").fetchall()
        assert len(rows) == 0
    finally:
        conn.close()
