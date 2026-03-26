import contextlib
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError


pytestmark = pytest.mark.unit


def test_create_data_table_rejects_invalid_string_column_hints() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_metadata_ops as data_table_metadata_ops_module,
    )

    db = SimpleNamespace(
        _get_current_utc_timestamp_str=lambda: "2026-03-21T00:00:00.000Z",
        _generate_uuid=lambda: "table-uuid",
        _resolve_data_tables_owner=lambda owner_user_id: None,
        client_id="client-1",
        transaction=lambda: (_ for _ in ()).throw(AssertionError("transaction should not start")),
    )

    with pytest.raises(InputError, match="Invalid column_hints JSON"):
        data_table_metadata_ops_module.create_data_table(
            db,
            name="Table",
            prompt="Prompt",
            column_hints="{bad-json",
        )


def test_update_data_table_rejects_invalid_string_column_hints() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_metadata_ops as data_table_metadata_ops_module,
    )

    db = SimpleNamespace(
        _resolve_data_tables_owner=lambda owner_user_id: None,
        execute_query=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("update query should not run for invalid column_hints")
        ),
        _get_current_utc_timestamp_str=lambda: "2026-03-21T00:00:00.000Z",
    )

    with pytest.raises(InputError, match="Invalid column_hints JSON"):
        data_table_metadata_ops_module.update_data_table(
            db,
            9,
            column_hints="{bad-json",
        )


def test_get_data_table_by_uuid_returns_none_for_empty_uuid() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_metadata_ops as data_table_metadata_ops_module,
    )

    db = SimpleNamespace(
        execute_query=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("query should not run for empty uuid")
        ),
    )

    assert data_table_metadata_ops_module.get_data_table_by_uuid(db, "") is None


@pytest.mark.parametrize(
    ("backend_type", "like_op"),
    [
        (BackendType.SQLITE, "LIKE"),
        (BackendType.POSTGRESQL, "ILIKE"),
    ],
)
def test_list_and_count_data_tables_preserve_filter_parity(
    backend_type: BackendType,
    like_op: str,
) -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_metadata_ops as data_table_metadata_ops_module,
    )

    execute_calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeCursor:
        def __init__(self, *, rows=None, row=None) -> None:
            self._rows = rows or []
            self._row = row

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return self._row

    def execute_query(query: str, params: tuple[object, ...]):
        execute_calls.append((" ".join(query.split()), params))
        if query.startswith("SELECT COUNT(*)"):
            return FakeCursor(row={"total": 2})
        return FakeCursor(rows=[{"id": 9}, {"id": 10}])

    db = SimpleNamespace(
        _resolve_data_tables_owner=lambda owner_user_id: "77",
        execute_query=execute_query,
        backend_type=backend_type,
    )

    listed = data_table_metadata_ops_module.list_data_tables(
        db,
        status="ready",
        search="alpha",
        workspace_tag="ws-1",
        limit=25,
        offset=5,
        include_deleted=False,
        owner_user_id=77,
    )
    total = data_table_metadata_ops_module.count_data_tables(
        db,
        status="ready",
        search="alpha",
        workspace_tag="ws-1",
        include_deleted=False,
        owner_user_id=77,
    )

    assert listed == [{"id": 9}, {"id": 10}]
    assert total == 2
    assert execute_calls == [
        (
            f"SELECT * FROM data_tables WHERE deleted = 0 AND client_id = ? AND status = ? AND workspace_tag = ? AND (name {like_op} ? OR description {like_op} ?) ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            ("77", "ready", "ws-1", "%alpha%", "%alpha%", 25, 5),
        ),
        (
            f"SELECT COUNT(*) as total FROM data_tables WHERE deleted = 0 AND client_id = ? AND status = ? AND workspace_tag = ? AND (name {like_op} ? OR description {like_op} ?)",
            ("77", "ready", "ws-1", "%alpha%", "%alpha%"),
        ),
    ]


@pytest.mark.parametrize("rowcount", [0, 1])
def test_soft_delete_data_table_only_cascades_when_parent_row_updated(rowcount: int) -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_metadata_ops as data_table_metadata_ops_module,
    )

    execute_calls: list[tuple[object, str, tuple[object, ...]]] = []
    child_calls: list[tuple[object, int, str, int | None]] = []
    conn = object()

    class FakeCursor:
        def __init__(self, rowcount: int) -> None:
            self.rowcount = rowcount

    @contextlib.contextmanager
    def transaction():
        yield conn

    def execute_with_connection(connection, query: str, params: tuple[object, ...]):
        execute_calls.append((connection, " ".join(query.split()), params))
        return FakeCursor(rowcount)

    def soft_delete_children(connection, table_id: int, now: str, *, owner_user_id: int | None = None):
        child_calls.append((connection, table_id, now, owner_user_id))

    db = SimpleNamespace(
        _get_current_utc_timestamp_str=lambda: "2026-03-21T00:00:00.000Z",
        _resolve_data_tables_owner=lambda owner_user_id: "77",
        transaction=transaction,
        _execute_with_connection=execute_with_connection,
        _soft_delete_data_table_children=soft_delete_children,
    )

    deleted = data_table_metadata_ops_module.soft_delete_data_table(
        db,
        9,
        owner_user_id=77,
    )

    assert deleted is (rowcount == 1)
    assert execute_calls == [
        (
            conn,
            "UPDATE data_tables SET deleted = 1, updated_at = ?, last_modified = ?, version = version + 1 WHERE id = ? AND deleted = 0 AND client_id = ?",
            ("2026-03-21T00:00:00.000Z", "2026-03-21T00:00:00.000Z", 9, "77"),
        )
    ]
    expected_child_calls = (
        [(conn, 9, "2026-03-21T00:00:00.000Z", 77)] if rowcount == 1 else []
    )
    assert child_calls == expected_child_calls
