import os
import sqlite3

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def test_sqlite_in_memory_creates_no_artifacts(tmp_path, monkeypatch):
    """Ensure ':memory:' connections do not create WAL/SHM or ':memory:' files."""

    # Isolate filesystem effects to a temp directory
    monkeypatch.chdir(tmp_path)

    # Sanity: ensure no pre-existing artifacts
    for name in (":memory:", ":memory:-wal", ":memory:-shm"):
        p = tmp_path / name
        if p.exists():
            p.unlink()
        assert not p.exists()

    db = MediaDatabase(db_path=":memory:", client_id="memtest")
    try:
        # Touch the DB with a simple statement and inspect journal mode
        with db.transaction() as conn:
            row = conn.execute("PRAGMA journal_mode").fetchone()
            # sqlite3.Row is iterable; first column holds the mode
            mode = str(row[0]).lower() if row else ""
            assert mode != "wal", "In-memory DB should not use WAL"

        # Ensure no artifacts were created in the working directory
        for name in (":memory:", ":memory:-wal", ":memory:-shm"):
            assert not (tmp_path / name).exists(), f"Unexpected artifact file: {name}"
    finally:
        db.close_connection()
