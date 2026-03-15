import importlib

import pytest

from tldw_Server_API.app.core.DB_Management import sqlite_policy
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.connection_pool import MultiDatabasePool
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import ClaimsRetriever


def _clear_memory_artifacts(base_dir):
    for name in (":memory:", ":memory:-wal", ":memory:-shm"):
        p = base_dir / name
        if p.exists():
            p.unlink()
        assert not p.exists()


def test_sqlite_in_memory_creates_no_artifacts(tmp_path, monkeypatch):
    """Ensure ':memory:' connections do not create WAL/SHM or ':memory:' files."""

    # Isolate filesystem effects to a temp directory
    monkeypatch.chdir(tmp_path)

    # Sanity: ensure no pre-existing artifacts
    _clear_memory_artifacts(tmp_path)

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


def test_claims_retriever_memory_path_creates_no_artifacts(tmp_path, monkeypatch):
    """ClaimsRetriever ':memory:' should not materialize a file-backed :memory: DB."""
    monkeypatch.chdir(tmp_path)
    _clear_memory_artifacts(tmp_path)

    retriever = ClaimsRetriever(":memory:")
    try:
        rows = retriever._execute_query("SELECT 1 as n")
        assert rows and rows[0]["n"] == 1
        for name in (":memory:", ":memory:-wal", ":memory:-shm"):
            assert not (tmp_path / name).exists(), f"Unexpected artifact file: {name}"
    finally:
        retriever.close()


def test_multi_database_pool_memory_path_creates_no_artifacts(tmp_path, monkeypatch):
    """MultiDatabasePool ':memory:' should remain in-memory without sidecar files."""
    monkeypatch.chdir(tmp_path)
    _clear_memory_artifacts(tmp_path)

    pool = MultiDatabasePool(default_config={"min_connections": 1, "max_connections": 2, "enable_wal": True})
    try:
        with pool.get_connection(":memory:") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS t(x INTEGER)")
            conn.execute("INSERT INTO t(x) VALUES (1)")
            row = conn.execute("SELECT COUNT(*) as c FROM t").fetchone()
            assert int(row[0]) == 1

        for name in (":memory:", ":memory:-wal", ":memory:-shm"):
            assert not (tmp_path / name).exists(), f"Unexpected artifact file: {name}"
    finally:
        pool.close_all()


def test_multi_database_pool_uses_shared_sqlite_policy_helper_for_wal_toggle(tmp_path):
    pool_module = importlib.import_module(
        "tldw_Server_API.app.core.RAG.rag_service.connection_pool"
    )
    calls: list[dict[str, object]] = []

    def fake_configure(conn, **kwargs):
        calls.append(kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sqlite_policy, "configure_sqlite_connection", fake_configure)
        pool_module = importlib.reload(pool_module)

        pool = pool_module.MultiDatabasePool(
            default_config={"min_connections": 1, "max_connections": 1, "enable_wal": False}
        )
        try:
            with pool.get_connection(str(tmp_path / "rag.db")) as conn:
                conn.execute("SELECT 1")
        finally:
            pool.close_all()

    importlib.reload(pool_module)

    assert calls
    assert all(
        call == {"use_wal": False, "synchronous": None}
        for call in calls
    )
