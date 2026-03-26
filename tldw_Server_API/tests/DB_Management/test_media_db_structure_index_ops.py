import contextlib
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError


pytestmark = pytest.mark.unit


def test_write_structure_index_records_clears_old_rows_before_inserting_new_ones() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        structure_index_ops as structure_index_ops_module,
    )

    execute_calls: list[tuple[str, tuple[object, ...]]] = []

    def execute_with_connection(conn, query: str, params: tuple[object, ...]):
        execute_calls.append((query, params))
        return SimpleNamespace()

    db = SimpleNamespace(
        _execute_with_connection=execute_with_connection,
        _get_current_utc_timestamp_str=lambda: "2026-03-21T00:00:00.000Z",
        client_id="client-1",
        backend_type=BackendType.SQLITE,
    )
    conn = object()
    records = [
        {
            "parent_id": None,
            "kind": "section",
            "level": 1,
            "title": "Root",
            "start_char": 0,
            "end_char": 10,
            "order_index": 0,
            "path": "root",
        },
        {
            "parent_id": 1,
            "kind": "section",
            "level": 2,
            "title": "Child",
            "start_char": 11,
            "end_char": 20,
            "order_index": 1,
            "path": "root/child",
        },
    ]

    inserted = structure_index_ops_module._write_structure_index_records(db, conn, 9, records)

    assert inserted == 2
    assert execute_calls[0] == (
        "DELETE FROM DocumentStructureIndex WHERE media_id = ?",
        (9,),
    )
    assert all("INSERT INTO DocumentStructureIndex" in call[0] for call in execute_calls[1:])
    assert execute_calls[1][1][-1] == 0


def test_write_structure_index_records_skips_invalid_rows_and_keeps_valid_ones() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        structure_index_ops as structure_index_ops_module,
    )

    execute_calls: list[tuple[str, tuple[object, ...]]] = []

    def execute_with_connection(conn, query: str, params: tuple[object, ...]):
        execute_calls.append((query, params))
        if "INSERT INTO DocumentStructureIndex" in query and params[4] == "Bad":
            raise ValueError("bad row")
        return SimpleNamespace()

    db = SimpleNamespace(
        _execute_with_connection=execute_with_connection,
        _get_current_utc_timestamp_str=lambda: "2026-03-21T00:00:00.000Z",
        client_id="client-1",
        backend_type=BackendType.POSTGRESQL,
    )
    conn = object()
    records = [
        {"title": "Good", "path": "good"},
        {"title": "Bad", "path": "bad"},
    ]

    inserted = structure_index_ops_module._write_structure_index_records(db, conn, 9, records)

    assert inserted == 1
    assert execute_calls[0] == (
        "DELETE FROM DocumentStructureIndex WHERE media_id = ?",
        (9,),
    )
    assert len(execute_calls) == 3
    assert execute_calls[1][1][-1] is False


def test_write_document_structure_index_validates_media_id_and_wraps_transaction() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        structure_index_ops as structure_index_ops_module,
    )

    transaction_calls: list[str] = []
    helper_calls: list[tuple[object, int, list[dict[str, object]]]] = []
    conn = object()

    @contextlib.contextmanager
    def transaction():
        transaction_calls.append("enter")
        yield conn
        transaction_calls.append("exit")

    def write_structure_index_records(inner_conn, media_id: int, records: list[dict[str, object]]):
        helper_calls.append((inner_conn, media_id, records))
        return 3

    db = SimpleNamespace(
        transaction=transaction,
        _write_structure_index_records=write_structure_index_records,
    )
    records = [{"path": "root"}]

    with pytest.raises(InputError):
        structure_index_ops_module.write_document_structure_index(db, 0, records)

    inserted = structure_index_ops_module.write_document_structure_index(db, 9, records)

    assert inserted == 3
    assert transaction_calls == ["enter", "exit"]
    assert helper_calls == [(conn, 9, records)]


def test_delete_document_structure_for_media_returns_rowcount_and_noops_for_falsey_media_id() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        structure_index_ops as structure_index_ops_module,
    )

    execute_calls: list[tuple[object, str, tuple[object, ...]]] = []
    conn = object()

    class FakeCursor:
        rowcount = 5

    @contextlib.contextmanager
    def transaction():
        yield conn

    def execute_with_connection(connection, query: str, params: tuple[object, ...]):
        execute_calls.append((connection, query, params))
        return FakeCursor()

    db = SimpleNamespace(
        transaction=transaction,
        _execute_with_connection=execute_with_connection,
    )

    assert structure_index_ops_module.delete_document_structure_for_media(db, 0) == 0
    assert structure_index_ops_module.delete_document_structure_for_media(db, 9) == 5
    assert execute_calls == [
        (
            conn,
            "DELETE FROM DocumentStructureIndex WHERE media_id = ?",
            (9,),
        )
    ]
