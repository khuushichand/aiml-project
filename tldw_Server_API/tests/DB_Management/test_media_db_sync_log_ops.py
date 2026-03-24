import contextlib
from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.unit


def test_get_sync_log_entries_decodes_payloads_and_preserves_limit_params() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_log_ops as sync_log_ops_module,
    )

    conn = object()
    fetch_calls: list[tuple[object, str, tuple[object, ...]]] = []

    def get_connection():
        return conn

    def fetchall_with_connection(connection, query: str, params: tuple[object, ...]):
        fetch_calls.append((connection, query, params))
        return [
            {"change_id": 1, "payload": '{"title":"one"}'},
            {"change_id": 2, "payload": "not-json"},
            {"change_id": 3, "payload": None},
        ]

    db = SimpleNamespace(
        get_connection=get_connection,
        _fetchall_with_connection=fetchall_with_connection,
        db_path_str=":memory:",
    )

    result = sync_log_ops_module.get_sync_log_entries(
        db,
        since_change_id=4,
        limit=2,
    )

    assert fetch_calls == [
        (
            conn,
            "SELECT change_id, entity, entity_uuid, operation, timestamp, client_id, version, "
            "org_id, team_id, payload FROM sync_log WHERE change_id > ? ORDER BY change_id ASC LIMIT ?",
            (4, 2),
        )
    ]
    assert result == [
        {"change_id": 1, "payload": {"title": "one"}},
        {"change_id": 2, "payload": None},
        {"change_id": 3, "payload": None},
    ]


def test_delete_sync_log_entries_returns_zero_for_empty_list() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_log_ops as sync_log_ops_module,
    )

    db = SimpleNamespace()

    assert sync_log_ops_module.delete_sync_log_entries(db, []) == 0


def test_delete_sync_log_entries_validates_ids_and_uses_placeholder_query() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_log_ops as sync_log_ops_module,
    )

    execute_calls: list[tuple[object, str, tuple[object, ...]]] = []
    conn = object()

    class FakeCursor:
        rowcount = 3

    @contextlib.contextmanager
    def transaction():
        yield conn

    def execute_with_connection(connection, query: str, params: tuple[object, ...]):
        execute_calls.append((connection, query, params))
        return FakeCursor()

    db = SimpleNamespace(
        transaction=transaction,
        _execute_with_connection=execute_with_connection,
        db_path_str=":memory:",
    )

    with pytest.raises(ValueError):
        sync_log_ops_module.delete_sync_log_entries(db, [1, "two", 3])  # type: ignore[list-item]

    deleted = sync_log_ops_module.delete_sync_log_entries(db, [2, 3, 5])

    assert deleted == 3
    assert execute_calls == [
        (
            conn,
            "DELETE FROM sync_log WHERE change_id IN (?,?,?)",
            (2, 3, 5),
        )
    ]


def test_delete_sync_log_entries_before_validates_threshold_and_uses_transaction_query() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        sync_log_ops as sync_log_ops_module,
    )

    execute_calls: list[tuple[object, str, tuple[object, ...]]] = []
    conn = object()

    class FakeCursor:
        rowcount = 4

    @contextlib.contextmanager
    def transaction():
        yield conn

    def execute_with_connection(connection, query: str, params: tuple[object, ...]):
        execute_calls.append((connection, query, params))
        return FakeCursor()

    db = SimpleNamespace(
        transaction=transaction,
        _execute_with_connection=execute_with_connection,
        db_path_str=":memory:",
    )

    with pytest.raises(ValueError):
        sync_log_ops_module.delete_sync_log_entries_before(db, -1)

    deleted = sync_log_ops_module.delete_sync_log_entries_before(db, 7)

    assert deleted == 4
    assert execute_calls == [
        (
            conn,
            "DELETE FROM sync_log WHERE change_id <= ?",
            (7,),
        )
    ]
