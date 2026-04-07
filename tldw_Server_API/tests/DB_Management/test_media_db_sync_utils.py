from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError


def test_sync_utility_ops_generate_uuid_returns_uuid4_string() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_utility_ops as sync_utility_ops_module,
    )

    value = sync_utility_ops_module._generate_uuid(SimpleNamespace())
    parsed = UUID(value)

    assert str(parsed) == value
    assert parsed.version == 4


def test_sync_utility_ops_get_current_timestamp_uses_utc_millisecond_format() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_utility_ops as sync_utility_ops_module,
    )

    value = sync_utility_ops_module._get_current_utc_timestamp_str(SimpleNamespace())

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", value)


def test_sync_utility_ops_get_next_version_returns_incremented_pair_for_active_row() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_utility_ops as sync_utility_ops_module,
    )

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE Media (id INTEGER PRIMARY KEY, version INTEGER, deleted INTEGER NOT NULL)")
    conn.execute("INSERT INTO Media (id, version, deleted) VALUES (1, 2, 0)")

    result = sync_utility_ops_module._get_next_version(SimpleNamespace(), conn, "Media", "id", 1)

    assert result == (2, 3)


def test_sync_utility_ops_get_next_version_returns_none_for_deleted_row() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_utility_ops as sync_utility_ops_module,
    )

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE Media (id INTEGER PRIMARY KEY, version INTEGER, deleted INTEGER NOT NULL)")
    conn.execute("INSERT INTO Media (id, version, deleted) VALUES (1, 2, 1)")

    result = sync_utility_ops_module._get_next_version(SimpleNamespace(), conn, "Media", "id", 1)

    assert result is None


def test_sync_utility_ops_get_next_version_returns_none_for_non_integer_version() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_utility_ops as sync_utility_ops_module,
    )

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE Media (id INTEGER PRIMARY KEY, version TEXT, deleted INTEGER NOT NULL)")
    conn.execute("INSERT INTO Media (id, version, deleted) VALUES (1, 'two', 0)")

    result = sync_utility_ops_module._get_next_version(SimpleNamespace(), conn, "Media", "id", 1)

    assert result is None


def test_sync_utility_ops_get_next_version_rejects_unsafe_identifier() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_utility_ops as sync_utility_ops_module,
    )

    conn = sqlite3.connect(":memory:")

    with pytest.raises(DatabaseError, match="Unsafe identifier"):
        sync_utility_ops_module._get_next_version(
            SimpleNamespace(),
            conn,
            "Media; DROP TABLE Media",
            "id",
            1,
        )


def test_sync_utility_ops_log_sync_event_sqlite_prunes_payload_and_normalizes_datetime() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_utility_ops as sync_utility_ops_module,
    )

    calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeConnection:
        def execute(self, query: str, params: tuple[object, ...]) -> None:
            calls.append((query, params))

    db = SimpleNamespace(
        backend_type=BackendType.SQLITE,
        client_id="tenant-42",
        _resolve_scope_ids=lambda: (11, 22),
        _get_current_utc_timestamp_str=lambda: "2026-03-21T12:34:56.789Z",
        _execute_with_connection=lambda *_args, **_kwargs: pytest.fail(
            "Postgres execution helper should not be used for SQLite"
        ),
    )

    sync_utility_ops_module._log_sync_event(
        db,
        FakeConnection(),
        "Media",
        "media-uuid",
        "update",
        4,
        payload={
            "title": "Example",
            "vector_embedding": [1, 2, 3],
            "updated_at": datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
        },
    )

    assert len(calls) == 1
    query, params = calls[0]
    assert "INSERT INTO sync_log" in query
    assert params[:8] == (
        "Media",
        "media-uuid",
        "update",
        "2026-03-21T12:34:56.789Z",
        "tenant-42",
        4,
        11,
        22,
    )
    assert json.loads(params[8]) == {
        "title": "Example",
        "updated_at": "2026-03-21T12:00:00+00:00",
    }


def test_sync_utility_ops_log_sync_event_postgres_routes_through_execute_helper() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_utility_ops as sync_utility_ops_module,
    )

    conn = object()
    calls: list[tuple[object, str, tuple[object, ...]]] = []

    def record(connection, query: str, params: tuple[object, ...]) -> None:
        calls.append((connection, query, params))

    db = SimpleNamespace(
        backend_type=BackendType.POSTGRESQL,
        client_id="tenant-42",
        _resolve_scope_ids=lambda: (11, 22),
        _get_current_utc_timestamp_str=lambda: "2026-03-21T12:34:56.789Z",
        _execute_with_connection=record,
    )

    sync_utility_ops_module._log_sync_event(
        db,
        conn,
        "Media",
        "media-uuid",
        "create",
        1,
        payload={"title": "Example"},
    )

    assert len(calls) == 1
    assert calls[0][0] is conn
    assert "INSERT INTO sync_log" in calls[0][1]
    assert calls[0][2][:8] == (
        "Media",
        "media-uuid",
        "create",
        "2026-03-21T12:34:56.789Z",
        "tenant-42",
        1,
        11,
        22,
    )


def test_sync_utility_ops_log_sync_event_returns_early_for_missing_identifiers() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_utility_ops as sync_utility_ops_module,
    )

    db = SimpleNamespace(
        backend_type=BackendType.SQLITE,
        client_id="tenant-42",
        _resolve_scope_ids=lambda: (11, 22),
        _get_current_utc_timestamp_str=lambda: "2026-03-21T12:34:56.789Z",
        _execute_with_connection=lambda *_args, **_kwargs: pytest.fail("unexpected postgres write"),
    )

    class FailingConnection:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("sync log should not write when identifiers are missing")

    sync_utility_ops_module._log_sync_event(
        db,
        FailingConnection(),
        "",
        "media-uuid",
        "update",
        1,
        payload={"title": "ignored"},
    )
