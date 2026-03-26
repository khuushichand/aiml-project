from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)


pytestmark = pytest.mark.unit


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-analytics-helper")
    db.initialize_db()
    return db


def test_create_claims_analytics_export_returns_freshly_readable_row(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claims-analytics-create.db")
    try:
        row = db.create_claims_analytics_export(
            export_id="exp-create-1",
            user_id="1",
            format="json",
            status="ready",
            payload_json='{"events":[]}',
            filters_json='{"severity":"high"}',
            pagination_json='{"limit":10}',
        )

        assert row["export_id"] == "exp-create-1"
        assert row["user_id"] == "1"
        assert row["format"] == "json"
        assert row["status"] == "ready"
        assert row["payload_json"] == '{"events":[]}'
        assert row["filters_json"] == '{"severity":"high"}'
        assert row["pagination_json"] == '{"limit":10}'
        assert row["created_at"]
        assert row["updated_at"]
    finally:
        db.close_connection()


def test_get_claims_analytics_export_honors_optional_user_id_filter(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claims-analytics-get.db")
    try:
        db.create_claims_analytics_export(
            export_id="exp-get-1",
            user_id="1",
            format="csv",
            status="ready",
            payload_csv="id,value\n1,test\n",
        )

        assert db.get_claims_analytics_export("exp-get-1", user_id="2") == {}
        row = db.get_claims_analytics_export("exp-get-1", user_id="1")

        assert row["export_id"] == "exp-get-1"
        assert row["user_id"] == "1"
        assert row["payload_csv"] == "id,value\n1,test\n"
    finally:
        db.close_connection()


def test_claims_analytics_export_list_and_count_stay_in_filter_parity(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claims-analytics-list.db")
    try:
        db.create_claims_analytics_export(
            export_id="exp-ready-json",
            user_id="1",
            format="json",
            status="ready",
        )
        db.create_claims_analytics_export(
            export_id="exp-ready-csv",
            user_id="1",
            format="csv",
            status="ready",
        )
        db.create_claims_analytics_export(
            export_id="exp-failed-json",
            user_id="1",
            format="json",
            status="failed",
        )
        db.create_claims_analytics_export(
            export_id="exp-other-user",
            user_id="2",
            format="json",
            status="ready",
        )

        rows = db.list_claims_analytics_exports(
            "1",
            status="ready",
            format="json",
            limit=50,
            offset=0,
        )
        total = db.count_claims_analytics_exports("1", status="ready", format="json")

        assert [row["export_id"] for row in rows] == ["exp-ready-json"]
        assert total == len(rows) == 1
    finally:
        db.close_connection()


@pytest.mark.parametrize("retention_hours", ["oops", None, 0, -4])
def test_cleanup_claims_analytics_exports_rejects_invalid_retention(
    tmp_path: Path,
    retention_hours: object,
) -> None:
    db = _make_db(tmp_path, "claims-analytics-cleanup.db")
    try:
        db.create_claims_analytics_export(
            export_id="exp-cleanup-1",
            user_id="1",
            format="json",
            status="ready",
        )

        assert db.cleanup_claims_analytics_exports(
            user_id="1",
            retention_hours=retention_hours,  # type: ignore[arg-type]
        ) == 0
        assert db.count_claims_analytics_exports("1") == 1
    finally:
        db.close_connection()
