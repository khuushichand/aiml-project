from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import json
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError


pytestmark = pytest.mark.unit


def _load_data_table_replace_ops_module():
    module_name = "tldw_Server_API.app.core.DB_Management.media_db.runtime.data_table_replace_ops"
    assert importlib.util.find_spec(module_name) is not None
    return importlib.import_module(module_name)


def test_replace_data_table_contents_rebinds_on_media_database() -> None:
    from tldw_Server_API.app.core.DB_Management.media_db.media_database import MediaDatabase

    data_table_replace_ops_module = _load_data_table_replace_ops_module()

    assert (
        MediaDatabase.replace_data_table_contents
        is data_table_replace_ops_module.replace_data_table_contents
    )


def test_replace_data_table_contents_rejects_blank_owner_user_id() -> None:
    data_table_replace_ops_module = _load_data_table_replace_ops_module()

    with pytest.raises(InputError, match="owner_user_id is required"):
        data_table_replace_ops_module.replace_data_table_contents(
            SimpleNamespace(),
            9,
            owner_user_id="   ",
            columns=[{"name": "Name", "type": "text"}],
            rows=[{"row_json": {"col_a": "value"}}],
        )


def test_replace_data_table_contents_rejects_missing_columns() -> None:
    data_table_replace_ops_module = _load_data_table_replace_ops_module()

    with pytest.raises(InputError, match="columns are required"):
        data_table_replace_ops_module.replace_data_table_contents(
            SimpleNamespace(),
            9,
            owner_user_id="77",
            columns=[],
            rows=[{"row_json": {"col_a": "value"}}],
        )


def test_replace_data_table_contents_rejects_rows_is_none() -> None:
    data_table_replace_ops_module = _load_data_table_replace_ops_module()

    with pytest.raises(InputError, match="rows are required"):
        data_table_replace_ops_module.replace_data_table_contents(
            SimpleNamespace(),
            9,
            owner_user_id="77",
            columns=[{"name": "Name", "type": "text"}],
            rows=None,
        )


def test_replace_data_table_contents_rejects_owner_mismatch() -> None:
    data_table_replace_ops_module = _load_data_table_replace_ops_module()

    db = SimpleNamespace(
        _resolve_data_table_write_client_id=lambda *_args, **_kwargs: "77",
        _get_current_utc_timestamp_str=lambda: "2026-03-22T19:00:00.000Z",
        _generate_uuid=lambda: "generated-1",
        _normalize_data_table_row_json=lambda row_json, **_kwargs: json.dumps(row_json),
        transaction=lambda: contextlib.nullcontext(object()),
        _get_data_table_owner_client_id=lambda conn, table_id: "88",
        _execute_with_connection=lambda *_args, **_kwargs: None,
        execute_many=lambda *_args, **_kwargs: None,
    )

    with pytest.raises(InputError, match="data_table_owner_mismatch"):
        data_table_replace_ops_module.replace_data_table_contents(
            db,
            9,
            owner_user_id="77",
            columns=[{"name": "Name", "type": "text"}],
            rows=[{"row_json": {"col_a": "value"}}],
        )


def test_replace_data_table_contents_soft_deletes_and_reinserts_columns_and_rows() -> None:
    data_table_replace_ops_module = _load_data_table_replace_ops_module()

    execute_calls: list[tuple[str, tuple[object, ...]]] = []
    execute_many_calls: list[tuple[str, tuple[tuple[object, ...], ...], dict[str, object]]] = []
    generated_ids: list[str] = []

    class _FakeTransaction:
        def __enter__(self):
            return "conn"

        def __exit__(self, exc_type, exc, tb):
            return False

    def _generate_uuid() -> str:
        value = f"generated-{len(generated_ids) + 1}"
        generated_ids.append(value)
        return value

    def _normalize_data_table_row_json(row_json, *, column_ids=None, validate_keys=False):
        assert validate_keys is True
        assert column_ids == {"generated-1"}
        return json.dumps(row_json)

    db = SimpleNamespace(
        _resolve_data_table_write_client_id=lambda *_args, **_kwargs: "77",
        _get_current_utc_timestamp_str=lambda: "2026-03-22T19:00:00.000Z",
        _generate_uuid=_generate_uuid,
        _normalize_data_table_row_json=_normalize_data_table_row_json,
        transaction=lambda: _FakeTransaction(),
        _get_data_table_owner_client_id=lambda conn, table_id: "77",
        _execute_with_connection=lambda conn, query, params: execute_calls.append(
            (" ".join(query.split()), params)
        ),
        execute_many=lambda query, rows, **kwargs: execute_many_calls.append(
            (" ".join(query.split()), tuple(rows), kwargs)
        ),
    )

    result = data_table_replace_ops_module.replace_data_table_contents(
        db,
        9,
        owner_user_id="77",
        columns=[{"name": "Name", "type": "text"}],
        rows=[{"row_json": {"generated-1": "Alice"}}],
    )

    expected_row_json = json.dumps({"generated-1": "Alice"})
    expected_row_hash = hashlib.sha256(expected_row_json.encode("utf-8")).hexdigest()

    assert result == (1, 1)
    assert generated_ids == ["generated-1", "generated-2"]
    assert execute_calls == [
        (
            "UPDATE data_table_columns SET deleted = 1, last_modified = ?, version = version + 1 WHERE table_id = ? AND deleted = 0",
            ("2026-03-22T19:00:00.000Z", 9),
        ),
        (
            "UPDATE data_table_rows SET deleted = 1, last_modified = ?, version = version + 1 WHERE table_id = ? AND deleted = 0",
            ("2026-03-22T19:00:00.000Z", 9),
        ),
    ]
    assert execute_many_calls[0] == (
        "INSERT INTO data_table_columns ( table_id, column_id, name, type, description, format, position, created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                9,
                "generated-1",
                "Name",
                "text",
                None,
                None,
                0,
                "2026-03-22T19:00:00.000Z",
                "2026-03-22T19:00:00.000Z",
                1,
                "77",
                0,
                None,
                None,
            ),
        ),
        {"commit": False, "connection": "conn"},
    )
    assert execute_many_calls[1] == (
        "INSERT INTO data_table_rows ( table_id, row_id, row_index, row_json, row_hash, created_at, last_modified, version, client_id, deleted, prev_version, merge_parent_uuid ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                9,
                "generated-2",
                0,
                expected_row_json,
                expected_row_hash,
                "2026-03-22T19:00:00.000Z",
                "2026-03-22T19:00:00.000Z",
                1,
                "77",
                0,
                None,
                None,
            ),
        ),
        {"commit": False, "connection": "conn"},
    )
