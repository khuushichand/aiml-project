from __future__ import annotations

import contextlib
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError


pytestmark = pytest.mark.unit


def test_get_data_table_counts_aggregates_columns_and_sources() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_child_ops as data_table_child_ops_module,
    )

    execute_calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    def execute_query(query: str, params: tuple[object, ...]):
        execute_calls.append((" ".join(query.split()), params))
        if "FROM data_table_columns" in query:
            return FakeCursor([{"table_id": 9, "count": 2}])
        return FakeCursor([{"table_id": 9, "count": 1}, {"table_id": 10, "count": 4}])

    db = SimpleNamespace(
        _resolve_data_tables_owner=lambda owner_user_id: "77",
        execute_query=execute_query,
    )

    counts = data_table_child_ops_module.get_data_table_counts(
        db,
        [9, 10],
        owner_user_id=77,
    )

    assert counts == {
        9: {"column_count": 2, "source_count": 1},
        10: {"column_count": 0, "source_count": 4},
    }
    assert len(execute_calls) == 2
    assert execute_calls[0][1] == (9, 10, "77")
    assert execute_calls[1][1] == (9, 10, "77")


@pytest.mark.parametrize(
    ("helper_name", "payload_key", "payload"),
    [
        (
            "insert_data_table_columns",
            "columns",
            [{"name": "Name", "type": "text", "position": 0}],
        ),
        (
            "insert_data_table_rows",
            "rows",
            [{"row_index": 0, "row_json": {"col-1": "Alice"}}],
        ),
        (
            "insert_data_table_sources",
            "sources",
            [{"source_type": "chat", "source_id": "source-1"}],
        ),
    ],
)
def test_child_insert_methods_return_zero_when_owner_filter_does_not_own_table(
    helper_name: str,
    payload_key: str,
    payload: list[dict[str, object]],
) -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_child_ops as data_table_child_ops_module,
    )

    execute_calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeCursor:
        def fetchone(self):
            return None

    def execute_query(query: str, params: tuple[object, ...]):
        execute_calls.append((" ".join(query.split()), params))
        return FakeCursor()

    db = SimpleNamespace(
        _resolve_data_tables_owner=lambda owner_user_id: "77",
        execute_query=execute_query,
        _resolve_data_table_write_client_id=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("write-client resolution should not run when ownership check fails")
        ),
        list_data_table_columns=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("column listing should not run when ownership check fails")
        ),
        transaction=lambda: (_ for _ in ()).throw(
            AssertionError("transaction should not start when ownership check fails")
        ),
    )

    helper = getattr(data_table_child_ops_module, helper_name)
    result = helper(
        db,
        9,
        owner_user_id=77,
        **{payload_key: payload},
    )

    assert result == 0
    assert execute_calls == [
        ("SELECT 1 FROM data_tables WHERE id = ? AND client_id = ? LIMIT 1", (9, "77"))
    ]


def test_insert_data_table_rows_requires_columns_when_validate_keys_enabled() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_child_ops as data_table_child_ops_module,
    )

    db = SimpleNamespace(
        _resolve_data_tables_owner=lambda owner_user_id: None,
        _resolve_data_table_write_client_id=lambda *_args, **_kwargs: "77",
        list_data_table_columns=lambda *_args, **_kwargs: [],
    )

    with pytest.raises(InputError, match="data_table_columns_required"):
        data_table_child_ops_module.insert_data_table_rows(
            db,
            9,
            [{"row_index": 0, "row_json": {"col-1": "Alice"}}],
        )


def test_list_data_table_rows_normalizes_limit_offset_and_preserves_ordering() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_child_ops as data_table_child_ops_module,
    )

    execute_calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeCursor:
        def fetchall(self):
            return [{"row_id": "row-1"}]

    def execute_query(query: str, params: tuple[object, ...]):
        execute_calls.append((" ".join(query.split()), params))
        return FakeCursor()

    db = SimpleNamespace(
        _resolve_data_tables_owner=lambda owner_user_id: "77",
        execute_query=execute_query,
    )

    rows = data_table_child_ops_module.list_data_table_rows(
        db,
        9,
        limit=99999,
        offset=-4,
        owner_user_id=77,
    )

    assert rows == [{"row_id": "row-1"}]
    assert execute_calls == [
        (
            "SELECT * FROM data_table_rows WHERE table_id = ? AND deleted = 0 AND client_id = ? ORDER BY row_index ASC, id ASC LIMIT ? OFFSET ?",
            (9, "77", 2000, 0),
        )
    ]


@pytest.mark.parametrize(
    ("helper_name", "table_name"),
    [
        ("soft_delete_data_table_columns", "data_table_columns"),
        ("soft_delete_data_table_rows", "data_table_rows"),
        ("soft_delete_data_table_sources", "data_table_sources"),
    ],
)
def test_child_soft_delete_methods_return_cursor_rowcount(
    helper_name: str,
    table_name: str,
) -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_child_ops as data_table_child_ops_module,
    )

    execute_calls: list[tuple[str, tuple[object, ...], bool | None]] = []

    class FakeCursor:
        rowcount = 3

    def execute_query(query: str, params: tuple[object, ...], *, commit: bool | None = None):
        execute_calls.append((" ".join(query.split()), params, commit))
        return FakeCursor()

    db = SimpleNamespace(
        _get_current_utc_timestamp_str=lambda: "2026-03-21T00:00:00.000Z",
        _resolve_data_tables_owner=lambda owner_user_id: "77",
        execute_query=execute_query,
    )

    helper = getattr(data_table_child_ops_module, helper_name)
    deleted = helper(db, 9, owner_user_id=77)

    assert deleted == 3
    assert execute_calls == [
        (
            f"UPDATE {table_name} SET deleted = 1, last_modified = ?, version = version + 1 WHERE table_id = ? AND deleted = 0 AND client_id = ?",
            ("2026-03-21T00:00:00.000Z", 9, "77"),
            True,
        )
    ]
