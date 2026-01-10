from __future__ import annotations

import sqlite3


def test_sqlite_store_migrations_add_new_columns(tmp_path) -> None:


     db_path = tmp_path / "sandbox_store.db"
    # Create old schema missing runtime_version and resource_usage
    con = sqlite3.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE sandbox_runs (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            spec_version TEXT,
            runtime TEXT,
            base_image TEXT,
            phase TEXT,
            exit_code INTEGER,
            started_at TEXT,
            finished_at TEXT,
            message TEXT,
            image_digest TEXT,
            policy_hash TEXT
        );
        """
    )
    con.commit()
    con.close()

    # Instantiate store; should run ALTER TABLE migrations
    from tldw_Server_API.app.core.Sandbox.store import SQLiteStore

    SQLiteStore(db_path=str(db_path))

    # Verify columns exist
    con2 = sqlite3.connect(str(db_path))
    cur = con2.execute("PRAGMA table_info(sandbox_runs)")
    cols = {row[1] for row in cur.fetchall()}
    assert "runtime_version" in cols
    assert "resource_usage" in cols
    con2.close()
