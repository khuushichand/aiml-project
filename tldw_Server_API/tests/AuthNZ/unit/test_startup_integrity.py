import importlib
import sqlite3

import pytest

from tldw_Server_API.app.core.DB_Management import sqlite_policy
from tldw_Server_API.app.core.AuthNZ import startup_integrity


@pytest.mark.asyncio
async def test_startup_integrity_passes_for_healthy_sqlite_db(tmp_path):
    db_path = tmp_path / "users.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        conn.execute("INSERT INTO users (username) VALUES ('admin')")
        conn.commit()

    await startup_integrity.verify_authnz_sqlite_startup_integrity(
        database_url=f"sqlite:///{db_path}",
        auth_mode="single_user",
        dispatch_alerts=False,
    )


@pytest.mark.asyncio
async def test_startup_integrity_skips_missing_sqlite_db(tmp_path):
    db_path = tmp_path / "missing_users.db"

    await startup_integrity.verify_authnz_sqlite_startup_integrity(
        database_url=f"sqlite:///{db_path}",
        auth_mode="single_user",
        dispatch_alerts=False,
    )


@pytest.mark.asyncio
async def test_startup_integrity_dispatches_alert_and_fails_for_malformed_db(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "users.db"
    db_path.write_bytes(b"not-a-sqlite-db")

    dispatched: dict[str, str] = {}

    async def _fake_dispatch_integrity_alert(**kwargs):
        dispatched.update(kwargs)

    monkeypatch.setattr(
        startup_integrity,
        "_dispatch_integrity_alert",
        _fake_dispatch_integrity_alert,
    )

    with pytest.raises(RuntimeError, match="startup integrity check failed"):
        await startup_integrity.verify_authnz_sqlite_startup_integrity(
            database_url=f"sqlite:///{db_path}",
            auth_mode="single_user",
            dispatch_alerts=True,
            fail_on_error=True,
        )

    assert dispatched["db_path"] == str(db_path)
    assert "database" in dispatched["quick_check_result"].lower()


@pytest.mark.asyncio
async def test_startup_integrity_fail_open_mode_allows_startup(tmp_path):
    db_path = tmp_path / "users.db"
    db_path.write_bytes(b"not-a-sqlite-db")

    await startup_integrity.verify_authnz_sqlite_startup_integrity(
        database_url=f"sqlite:///{db_path}",
        auth_mode="single_user",
        dispatch_alerts=False,
        fail_on_error=False,
    )


@pytest.mark.asyncio
async def test_startup_integrity_skips_postgres_backend():
    await startup_integrity.verify_authnz_sqlite_startup_integrity(
        database_url="postgresql://user:pass@localhost:5432/tldw",
        auth_mode="multi_user",
        dispatch_alerts=False,
    )


def test_startup_integrity_readonly_check_uses_shared_sqlite_policy_helper(tmp_path):
    module = importlib.import_module("tldw_Server_API.app.core.AuthNZ.startup_integrity")
    calls: list[dict[str, object]] = []

    def fake_configure(conn, **kwargs):
        calls.append(kwargs)

    db_path = tmp_path / "users.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        conn.execute("INSERT INTO users (username) VALUES ('admin')")
        conn.commit()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sqlite_policy, "configure_sqlite_connection", fake_configure)
        module = importlib.reload(module)
        rows = module._run_sqlite_pragma_check(
            db_path=db_path,
            pragma_sql="PRAGMA quick_check;",
            timeout_seconds=0.25,
        )

    importlib.reload(module)

    assert rows == ["ok"]
    assert calls == [{
        "use_wal": False,
        "synchronous": None,
        "busy_timeout_ms": 250,
        "foreign_keys": False,
        "temp_store": None,
    }]
