from __future__ import annotations

import importlib
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)


pytestmark = pytest.mark.unit


_RUNTIME_MODULE_NAME = (
    "tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_write_ops"
)


def _load_runtime_module():
    try:
        return importlib.import_module(_RUNTIME_MODULE_NAME)
    except ModuleNotFoundError:
        return None


def _load_helper(name: str):
    module = _load_runtime_module()
    if module is None:
        return None
    return getattr(module, name, None)


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="client-1")
    db.initialize_db()
    return db


def _fake_transaction(conn: object):
    @contextmanager
    def _tx():
        yield conn

    return _tx


def test_claims_write_helpers_rebind_on_media_database(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claims-write-rebind.db")
    try:
        runtime_module = _load_runtime_module()
        assert runtime_module is not None

        assert db.upsert_claims.__func__ is getattr(runtime_module, "upsert_claims", None)
        assert db.update_claim.__func__ is getattr(runtime_module, "update_claim", None)
        assert db.update_claim_review.__func__ is getattr(
            runtime_module, "update_claim_review", None
        )
        assert db.soft_delete_claims_for_media.__func__ is getattr(
            runtime_module, "soft_delete_claims_for_media", None
        )
    finally:
        db.close_connection()


def test_upsert_claims_returns_zero_for_empty_input() -> None:
    runtime_module = _load_runtime_module()
    assert runtime_module is not None

    db = SimpleNamespace(
        execute_many=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("execute_many should not run for empty claim batches")
        )
    )

    assert runtime_module.upsert_claims(db, []) == 0


def test_upsert_claims_applies_defaults_and_returns_insert_count() -> None:
    runtime_module = _load_runtime_module()
    assert runtime_module is not None

    conn = object()
    execute_many_calls: list[tuple[str, tuple[tuple[object, ...], ...], dict[str, object]]] = []

    def execute_many(query: str, rows, *, commit: bool = False, connection=None):
        execute_many_calls.append((query, tuple(rows), {"commit": commit, "connection": connection}))
        return SimpleNamespace(rowcount=len(rows))

    db = SimpleNamespace(
        client_id="client-1",
        transaction=_fake_transaction(conn),
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00.000Z",
        _generate_uuid=lambda: "generated-uuid-1",
        execute_many=execute_many,
    )

    inserted = runtime_module.upsert_claims(
        db,
        [
            {
                "media_id": 7,
                "chunk_index": 2,
                "claim_text": "alpha",
                "chunk_hash": "hash-alpha",
            }
        ],
    )

    assert inserted == 1
    assert len(execute_many_calls) == 1
    query, rows, metadata = execute_many_calls[0]
    assert "INSERT INTO Claims" in query
    assert "extractor, extractor_version" in query
    assert metadata == {"commit": False, "connection": conn}
    assert rows == (
        (
            7,
            2,
            None,
            None,
            "alpha",
            None,
            "heuristic",
            "v1",
            "hash-alpha",
            "generated-uuid-1",
            "2026-03-22T00:00:00.000Z",
            1,
            "client-1",
            None,
            None,
            None,
            None,
        ),
    )


def test_update_claim_returns_current_row_when_no_fields_change() -> None:
    runtime_module = _load_runtime_module()
    assert runtime_module is not None

    current_row = {"id": 11, "claim_text": "alpha", "version": 3}
    db = SimpleNamespace(
        get_claim_with_media=lambda claim_id, *, include_deleted=False: current_row,
        execute_query=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("execute_query should not run for no-op claim updates")
        ),
    )

    assert runtime_module.update_claim(db, 11) is current_row


def test_update_claim_refreshes_postgres_fts_only_for_text_changes() -> None:
    runtime_module = _load_runtime_module()
    assert runtime_module is not None

    execute_calls: list[tuple[str, tuple[object, ...], bool]] = []

    def execute_query(query: str, params: tuple[object, ...], *, commit: bool = False):
        execute_calls.append((" ".join(query.split()), params, commit))
        return SimpleNamespace(rowcount=1)

    db = SimpleNamespace(
        backend_type=BackendType.POSTGRESQL,
        client_id="client-1",
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00.000Z",
        execute_query=execute_query,
        get_claim_with_media=lambda claim_id, *, include_deleted=False: {
            "id": claim_id,
            "claim_text": "updated alpha",
        },
    )

    no_text_change = runtime_module.update_claim(
        db,
        11,
        deleted=True,
    )

    assert no_text_change == {"id": 11, "claim_text": "updated alpha"}
    assert len(execute_calls) == 1
    assert "UPDATE Claims SET" in execute_calls[0][0]
    assert "claims_fts_tsv" not in execute_calls[0][0]

    execute_calls.clear()

    result = runtime_module.update_claim(
        db,
        11,
        claim_text="updated alpha",
        span_start=1,
        span_end=5,
        confidence=0.9,
        extractor="manual",
        extractor_version="v2",
        deleted=False,
    )

    assert result == {"id": 11, "claim_text": "updated alpha"}
    assert len(execute_calls) == 2
    assert execute_calls[0] == (
        "UPDATE Claims SET claim_text = ?, span_start = ?, span_end = ?, confidence = ?, extractor = ?, extractor_version = ?, deleted = ?, last_modified = ?, version = version + 1, client_id = ? WHERE id = ?",
        (
            "updated alpha",
            1,
            5,
            0.9,
            "manual",
            "v2",
            0,
            "2026-03-22T00:00:00.000Z",
            "client-1",
            11,
        ),
        True,
    )
    assert any("claims_fts_tsv" in query for query, _params, _commit in execute_calls)


def test_update_claim_review_returns_conflict_when_versions_do_not_match() -> None:
    runtime_module = _load_runtime_module()
    assert runtime_module is not None

    conn = object()
    db = SimpleNamespace(
        transaction=_fake_transaction(conn),
        _fetchone_with_connection=lambda _conn, _query, _params: {
            "id": 11,
            "review_version": 3,
            "claim_text": "alpha",
        },
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00.000Z",
        _execute_with_connection=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("execute should not run on review-version conflict")
        ),
        get_claim_with_media=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("readback should not run on review-version conflict")
        ),
    )

    result = runtime_module.update_claim_review(
        db,
        11,
        review_status="approved",
        expected_version=2,
    )

    assert result == {"conflict": True, "current": {"id": 11, "review_version": 3, "claim_text": "alpha"}}


def test_update_claim_review_writes_review_log_and_refreshes_postgres_fts_on_corrected_text() -> None:
    runtime_module = _load_runtime_module()
    assert runtime_module is not None

    conn = object()
    execute_calls: list[tuple[str, tuple[object, ...], bool]] = []

    class _Cursor:
        def __init__(self, rowcount: int = 1) -> None:
            self.rowcount = rowcount

    def _fetchone_with_connection(_conn, query: str, params: tuple[object, ...]):
        assert _conn is conn
        assert query == "SELECT * FROM Claims WHERE id = ?"
        assert params == (11,)
        return {
            "id": 11,
            "review_version": 1,
            "review_status": "pending",
            "claim_text": "alpha",
            "reviewer_id": 42,
            "review_group": "alpha",
        }

    def _execute_with_connection(_conn, query: str, params: tuple[object, ...]):
        assert _conn is conn
        execute_calls.append((" ".join(query.split()), params, False))
        return _Cursor()

    db = SimpleNamespace(
        backend_type=BackendType.POSTGRESQL,
        client_id="client-1",
        transaction=_fake_transaction(conn),
        _fetchone_with_connection=_fetchone_with_connection,
        _execute_with_connection=_execute_with_connection,
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00.000Z",
        get_claim_with_media=lambda claim_id, *, include_deleted=False: {
            "id": claim_id,
            "claim_text": "updated alpha",
            "review_status": "approved",
        },
    )

    result = runtime_module.update_claim_review(
        db,
        11,
        review_status="approved",
        reviewer_id=43,
        review_group="alpha",
        review_notes="looks good",
        review_reason_code="ok",
        corrected_text="updated alpha",
        span_start=1,
        span_end=5,
        expected_version=1,
        action_ip="127.0.0.1",
        action_user_agent="pytest",
    )

    assert result == {"id": 11, "claim_text": "updated alpha", "review_status": "approved"}
    assert any("UPDATE Claims SET" in query and "review_version = review_version + 1" in query for query, _params, _commit in execute_calls)
    assert any("claims_fts_tsv" in query for query, _params, _commit in execute_calls)
    assert any("INSERT INTO claims_review_log" in query for query, _params, _commit in execute_calls)


def test_update_claim_review_returns_current_row_when_no_fields_change() -> None:
    runtime_module = _load_runtime_module()
    assert runtime_module is not None

    row = {
        "id": 11,
        "review_version": 1,
        "review_status": "pending",
        "claim_text": "alpha",
    }
    db = SimpleNamespace(
        transaction=_fake_transaction(object()),
        _fetchone_with_connection=lambda *_args, **_kwargs: row,
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00.000Z",
        _execute_with_connection=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("update should not run when no review fields change")
        ),
        get_claim_with_media=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("readback should not run when no review fields change")
        ),
    )

    assert runtime_module.update_claim_review(db, 11) == row


@pytest.mark.parametrize(
    ("backend_type", "expect_sqlite_cleanup"),
    [
        (BackendType.SQLITE, True),
        (BackendType.POSTGRESQL, False),
    ],
)
def test_soft_delete_claims_for_media_respects_backend_specific_cleanup(
    backend_type: BackendType,
    expect_sqlite_cleanup: bool,
) -> None:
    runtime_module = _load_runtime_module()
    assert runtime_module is not None

    conn = object()
    execute_calls: list[str] = []

    class _Cursor:
        def __init__(self, rowcount: int) -> None:
            self.rowcount = rowcount

    @contextmanager
    def transaction():
        yield conn

    def _execute_with_connection(_conn, query: str, params: tuple[object, ...]):
        assert _conn is conn
        execute_calls.append(" ".join(query.split()))
        return _Cursor(2)

    db = SimpleNamespace(
        backend_type=backend_type,
        client_id="client-1",
        transaction=transaction,
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00.000Z",
        _execute_with_connection=_execute_with_connection,
    )

    deleted = runtime_module.soft_delete_claims_for_media(db, 37)

    assert deleted == 2
    assert any("UPDATE Claims SET deleted = 1" in query for query in execute_calls)
    if expect_sqlite_cleanup:
        assert any("claims_fts(claims_fts, rowid, claim_text)" in query for query in execute_calls)
    else:
        assert not any("claims_fts(claims_fts, rowid, claim_text)" in query for query in execute_calls)
