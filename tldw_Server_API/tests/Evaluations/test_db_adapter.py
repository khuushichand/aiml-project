import importlib

import pytest

from tldw_Server_API.app.core.DB_Management import sqlite_policy


@pytest.mark.unit
def test_sqlite_adapter_uses_shared_sqlite_policy_helper(tmp_path):
    db_adapter_module = importlib.import_module(
        "tldw_Server_API.app.core.Evaluations.db_adapter"
    )
    calls: list[dict[str, object]] = []

    def fake_configure(conn, **kwargs):
        calls.append(kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sqlite_policy, "configure_sqlite_connection", fake_configure)
        db_adapter_module = importlib.reload(db_adapter_module)

        config = db_adapter_module.DatabaseConfig(
            db_type=db_adapter_module.DatabaseType.SQLITE,
            connection_string=str(tmp_path / "evaluations.db"),
        )
        adapter = db_adapter_module.SQLiteAdapter(config)
        try:
            assert adapter.conn.execute("PRAGMA mmap_size").fetchone()[0] == 268435456
        finally:
            adapter.close()

    importlib.reload(db_adapter_module)

    assert calls == [{"busy_timeout_ms": 30000}]
