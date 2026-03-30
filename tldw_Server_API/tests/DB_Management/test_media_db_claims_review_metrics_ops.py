from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_review_metrics_ops import (
    get_claims_review_extractor_metrics_daily as helper_get_claims_review_extractor_metrics_daily,
    list_claims_review_extractor_metrics_daily as helper_list_claims_review_extractor_metrics_daily,
    list_claims_review_user_ids as helper_list_claims_review_user_ids,
    upsert_claims_review_extractor_metrics_daily as helper_upsert_claims_review_extractor_metrics_daily,
)


pytestmark = pytest.mark.unit


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-review-metrics-helper")
    db.initialize_db()
    return db


def test_get_claims_review_extractor_metrics_daily_normalizes_none_version_and_missing_row(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-review-metrics-missing.db")
    try:
        assert (
            db.get_claims_review_extractor_metrics_daily.__func__
            is helper_get_claims_review_extractor_metrics_daily
        )
        assert db.get_claims_review_extractor_metrics_daily(
            user_id="1",
            report_date="2024-01-10",
            extractor="heuristic",
            extractor_version=None,
        ) == {}
    finally:
        db.close_connection()


def test_upsert_claims_review_extractor_metrics_daily_inserts_updates_and_normalizes_version(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-review-metrics-upsert.db")
    try:
        assert (
            db.upsert_claims_review_extractor_metrics_daily.__func__
            is helper_upsert_claims_review_extractor_metrics_daily
        )

        created = db.upsert_claims_review_extractor_metrics_daily(
            user_id="1",
            report_date="2024-01-10",
            extractor="heuristic",
            extractor_version=None,
            total_reviewed=10,
            approved_count=7,
            rejected_count=2,
            flagged_count=1,
            reassigned_count=0,
            edited_count=1,
            reason_code_counts_json='{"spam": 2}',
        )
        updated = db.upsert_claims_review_extractor_metrics_daily(
            user_id="1",
            report_date="2024-01-10",
            extractor="heuristic",
            extractor_version=None,
            total_reviewed=12,
            approved_count=8,
            rejected_count=2,
            flagged_count=1,
            reassigned_count=1,
            edited_count=2,
            reason_code_counts_json='{"spam": 3}',
        )

        assert created["extractor_version"] == ""
        assert updated["extractor_version"] == ""
        assert int(updated["id"]) == int(created["id"])
        assert int(updated["total_reviewed"]) == 12
        assert int(updated["edited_count"]) == 2
        assert updated["reason_code_counts_json"] == '{"spam": 3}'
    finally:
        db.close_connection()


def test_list_claims_review_extractor_metrics_daily_clamps_limit_and_offset(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-review-metrics-list.db")
    try:
        assert (
            db.list_claims_review_extractor_metrics_daily.__func__
            is helper_list_claims_review_extractor_metrics_daily
        )

        db.upsert_claims_review_extractor_metrics_daily(
            user_id="1",
            report_date="2024-01-10",
            extractor="heuristic",
            extractor_version="v1",
            total_reviewed=1,
        )
        db.upsert_claims_review_extractor_metrics_daily(
            user_id="1",
            report_date="2024-01-11",
            extractor="heuristic",
            extractor_version="v1",
            total_reviewed=2,
        )

        rows = db.list_claims_review_extractor_metrics_daily(
            user_id="1",
            limit=0,
            offset=-5,
        )

        assert len(rows) == 1
        assert rows[0]["report_date"] == "2024-01-11"
    finally:
        db.close_connection()


def test_list_claims_review_user_ids_returns_empty_for_non_postgres(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claims-review-user-ids-sqlite.db")
    try:
        assert db.list_claims_review_user_ids.__func__ is helper_list_claims_review_user_ids
        assert db.list_claims_review_user_ids() == []
    finally:
        db.close_connection()


def test_upsert_claims_review_metrics_existing_id_and_review_user_ids_preserve_tuple_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Cursor:
        def __init__(self, *, one=None, all_rows=None):
            self._one = one
            self._all = all_rows or []

        def fetchone(self):
            return self._one

        def fetchall(self):
            return self._all

    execute_calls: list[tuple[str, tuple[object, ...] | None, bool]] = []

    def _execute_query(sql, params=None, commit=False):
        execute_calls.append((sql, params, commit))
        if sql.startswith("SELECT id FROM claims_review_extractor_metrics_daily"):
            return _Cursor(one=(9,))
        if sql.startswith("UPDATE claims_review_extractor_metrics_daily SET"):
            return _Cursor()
        if sql.startswith("SELECT id, user_id, report_date"):
            return _Cursor(
                one={
                    "id": 9,
                    "user_id": "1",
                    "report_date": "2024-01-10",
                    "extractor": "heuristic",
                    "extractor_version": "",
                    "total_reviewed": 12,
                    "approved_count": 8,
                    "rejected_count": 2,
                    "flagged_count": 1,
                    "reassigned_count": 1,
                    "edited_count": 2,
                    "reason_code_counts_json": '{"spam": 3}',
                    "created_at": "2026-03-22T00:00:00Z",
                    "updated_at": "2026-03-22T00:00:01Z",
                }
            )
        if sql.startswith("SELECT DISTINCT COALESCE(CAST(m.owner_user_id AS TEXT), m.client_id) AS user_id"):
            return _Cursor(all_rows=[("1",), (None,), ("",), ("2",)])
        raise AssertionError(f"Unexpected SQL: {sql}")

    fake_db = SimpleNamespace(
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:01Z",
        execute_query=_execute_query,
        backend_type=BackendType.POSTGRESQL,
    )
    monkeypatch.setattr(
        fake_db,
        "get_claims_review_extractor_metrics_daily",
        lambda **kwargs: helper_get_claims_review_extractor_metrics_daily(fake_db, **kwargs),
        raising=False,
    )

    updated = helper_upsert_claims_review_extractor_metrics_daily(
        fake_db,
        user_id="1",
        report_date="2024-01-10",
        extractor="heuristic",
        extractor_version=None,
        total_reviewed=12,
        approved_count=8,
        rejected_count=2,
        flagged_count=1,
        reassigned_count=1,
        edited_count=2,
        reason_code_counts_json='{"spam": 3}',
    )
    user_ids = helper_list_claims_review_user_ids(fake_db)

    assert int(updated["id"]) == 9
    assert updated["extractor_version"] == ""
    assert any(
        sql.startswith("UPDATE claims_review_extractor_metrics_daily SET") and params[-1] == 9
        for sql, params, _commit in execute_calls
        if params is not None
    )
    assert user_ids == ["1", "2"]
