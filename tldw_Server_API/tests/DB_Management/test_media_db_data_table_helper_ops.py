from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError


pytestmark = pytest.mark.unit


def test_resolve_data_tables_owner_prefers_explicit_owner_and_scope_fallbacks(monkeypatch) -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_helper_ops as data_table_helper_ops_module,
    )

    db = SimpleNamespace()

    monkeypatch.setattr(
        data_table_helper_ops_module,
        "get_scope",
        lambda: SimpleNamespace(is_admin=False, user_id=42),
    )
    assert data_table_helper_ops_module._resolve_data_tables_owner(db, 77) == "77"
    assert data_table_helper_ops_module._resolve_data_tables_owner(db, None) == "42"

    monkeypatch.setattr(
        data_table_helper_ops_module,
        "get_scope",
        lambda: SimpleNamespace(is_admin=True, user_id=99),
    )
    assert data_table_helper_ops_module._resolve_data_tables_owner(db, None) is None

    monkeypatch.setattr(data_table_helper_ops_module, "get_scope", lambda: None)
    assert data_table_helper_ops_module._resolve_data_tables_owner(db, None) is None


def test_resolve_data_table_write_client_id_prefers_explicit_owner() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_helper_ops as data_table_helper_ops_module,
    )

    db = SimpleNamespace(
        _resolve_data_tables_owner=lambda owner_user_id: "77",
        execute_query=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("table lookup should not run when explicit owner resolves")
        ),
    )

    assert (
        data_table_helper_ops_module._resolve_data_table_write_client_id(
            db,
            9,
            owner_user_id=77,
        )
        == "77"
    )


@pytest.mark.parametrize(
    ("row", "expected", "error_match"),
    [
        ({"client_id": " owner-1 "}, "owner-1", None),
        (None, None, "data_table_not_found"),
        ({"client_id": "   "}, None, "data_table_owner_missing"),
    ],
)
def test_resolve_data_table_write_client_id_uses_table_owner_and_existing_error_codes(
    row,
    expected: str | None,
    error_match: str | None,
) -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_helper_ops as data_table_helper_ops_module,
    )

    class FakeCursor:
        def fetchone(self):
            return row

    db = SimpleNamespace(
        _resolve_data_tables_owner=lambda owner_user_id: None,
        execute_query=lambda query, params: FakeCursor(),
    )

    if error_match is not None:
        with pytest.raises(InputError, match=error_match):
            data_table_helper_ops_module._resolve_data_table_write_client_id(
                db,
                9,
                owner_user_id=None,
            )
        return

    assert (
        data_table_helper_ops_module._resolve_data_table_write_client_id(
            db,
            9,
            owner_user_id=None,
        )
        == expected
    )


def test_get_data_table_owner_client_id_returns_string_or_none() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_helper_ops as data_table_helper_ops_module,
    )

    fetch_calls: list[tuple[object, str, tuple[object, ...]]] = []
    conn = object()

    def fetchone_with_connection(connection, query: str, params: tuple[object, ...]):
        fetch_calls.append((connection, query, params))
        return {"client_id": 123}

    db = SimpleNamespace(_fetchone_with_connection=fetchone_with_connection)

    assert data_table_helper_ops_module._get_data_table_owner_client_id(db, conn, 9) == "123"
    assert fetch_calls == [
        (
            conn,
            "SELECT client_id FROM data_tables WHERE id = ? AND deleted = 0",
            (9,),
        )
    ]

    db = SimpleNamespace(_fetchone_with_connection=lambda *_args, **_kwargs: None)
    assert data_table_helper_ops_module._get_data_table_owner_client_id(db, conn, 9) is None


def test_normalize_data_table_row_json_preserves_valid_json_payloads() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_helper_ops as data_table_helper_ops_module,
    )

    db = SimpleNamespace()

    assert (
        data_table_helper_ops_module._normalize_data_table_row_json(
            db,
            {"col-a": {"nested": True}},
            column_ids={"col-a"},
            validate_keys=True,
        )
        == '{"col-a": {"nested": true}}'
    )
    assert (
        data_table_helper_ops_module._normalize_data_table_row_json(
            db,
            '[{"col-a": "value"}]',
            validate_keys=False,
        )
        == '[{"col-a": "value"}]'
    )


@pytest.mark.parametrize(
    ("row_json", "column_ids", "validate_keys", "error_match"),
    [
        ('{"col-a":', {"col-a"}, True, "row_json must be valid JSON"),
        ('["value"]', {"col-a"}, True, "row_json must be an object keyed by column_id"),
        ({"col-b": "value"}, {"col-a"}, True, "row_json contains unknown column_id\\(s\\): col-b"),
    ],
)
def test_normalize_data_table_row_json_rejects_invalid_payloads(
    row_json,
    column_ids: set[str] | None,
    validate_keys: bool,
    error_match: str,
) -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_helper_ops as data_table_helper_ops_module,
    )

    db = SimpleNamespace()

    with pytest.raises(InputError, match=error_match):
        data_table_helper_ops_module._normalize_data_table_row_json(
            db,
            row_json,
            column_ids=column_ids,
            validate_keys=validate_keys,
        )


def test_soft_delete_data_table_children_updates_all_child_tables_and_preserves_owner_filter() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.runtime import (
        data_table_helper_ops as data_table_helper_ops_module,
    )

    execute_calls: list[tuple[object, str, tuple[object, ...]]] = []
    conn = object()

    def execute_with_connection(connection, query: str, params: tuple[object, ...]):
        execute_calls.append((connection, " ".join(query.split()), params))
        return SimpleNamespace()

    db = SimpleNamespace(
        _resolve_data_tables_owner=lambda owner_user_id: "77",
        _execute_with_connection=execute_with_connection,
    )

    data_table_helper_ops_module._soft_delete_data_table_children(
        db,
        conn,
        9,
        "2026-03-21T00:00:00.000Z",
        owner_user_id=77,
    )

    assert execute_calls == [
        (
            conn,
            "UPDATE data_table_columns SET deleted = 1, last_modified = ?, version = version + 1 WHERE table_id = ? AND deleted = 0 AND client_id = ?",
            ("2026-03-21T00:00:00.000Z", 9, "77"),
        ),
        (
            conn,
            "UPDATE data_table_rows SET deleted = 1, last_modified = ?, version = version + 1 WHERE table_id = ? AND deleted = 0 AND client_id = ?",
            ("2026-03-21T00:00:00.000Z", 9, "77"),
        ),
        (
            conn,
            "UPDATE data_table_sources SET deleted = 1, last_modified = ?, version = version + 1 WHERE table_id = ? AND deleted = 0 AND client_id = ?",
            ("2026-03-21T00:00:00.000Z", 9, "77"),
        ),
    ]
