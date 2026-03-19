from types import SimpleNamespace

import tldw_Server_API.app.core.DB_Management.Media_DB_v2 as media_db_module
import pytest
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.schema.bootstrap import ensure_media_schema
from tldw_Server_API.app.core.DB_Management.media_db.schema import bootstrap as bootstrap_module


@pytest.mark.unit
def test_ensure_media_schema_dispatches_sqlite(monkeypatch) -> None:
    db = SimpleNamespace(backend_type=BackendType.SQLITE)
    calls: list[object] = []

    monkeypatch.setattr(bootstrap_module, "initialize_sqlite_schema", lambda value: calls.append(value))
    monkeypatch.setattr(
        bootstrap_module,
        "initialize_postgres_schema",
        lambda value: pytest.fail(f"unexpected postgres dispatch for {value!r}"),
    )

    ensure_media_schema(db)

    assert calls == [db]


@pytest.mark.unit
def test_ensure_media_schema_dispatches_postgres(monkeypatch) -> None:
    db = SimpleNamespace(backend_type=BackendType.POSTGRESQL)
    calls: list[object] = []

    monkeypatch.setattr(
        bootstrap_module,
        "initialize_sqlite_schema",
        lambda value: pytest.fail(f"unexpected sqlite dispatch for {value!r}"),
    )
    monkeypatch.setattr(bootstrap_module, "initialize_postgres_schema", lambda value: calls.append(value))

    ensure_media_schema(db)

    assert calls == [db]


@pytest.mark.unit
def test_initialize_schema_uses_bootstrap_entrypoint(monkeypatch) -> None:
    db = MediaDatabase.__new__(MediaDatabase)
    db.backend_type = BackendType.SQLITE
    calls: list[object] = []

    monkeypatch.setattr(media_db_module, "ensure_media_schema", lambda value: calls.append(value))

    MediaDatabase._initialize_schema(db)

    assert calls == [db]


@pytest.mark.integration
def test_ensure_media_schema_keeps_sqlite_schema_intact() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="schema-bootstrap")
    try:
        ensure_media_schema(db)

        table = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Media'"
        ).fetchone()
        version = db.execute_query("SELECT version FROM schema_version").fetchone()

        assert table is not None
        assert version["version"] == db._CURRENT_SCHEMA_VERSION
    finally:
        db.close_connection()
