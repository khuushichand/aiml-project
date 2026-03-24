from __future__ import annotations

import importlib
import json
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError
from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase


pytestmark = pytest.mark.unit


def _load_query_ops_module():
    return importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.email_query_ops"
    )


def _add_email_media(
    db: MediaDatabase,
    *,
    url: str,
    title: str,
    content: str,
    safe_metadata: dict | None = None,
) -> int:
    media_id, _media_uuid, _msg = db.add_media_with_keywords(
        url=url,
        title=title,
        media_type="email",
        content=content,
        keywords=["email"],
        author="tester@example.com",
        safe_metadata=json.dumps(safe_metadata) if isinstance(safe_metadata, dict) else None,
    )
    assert media_id is not None
    return int(media_id)


def test_parse_email_operator_query_rejects_parentheses_and_preserves_unknown_and_relative_terms() -> None:
    query_ops_module = _load_query_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-query-parse-test")
    try:
        with pytest.raises(InputError):
            query_ops_module._parse_email_operator_query(db, "(budget)")

        parsed = query_ops_module._parse_email_operator_query(
            db,
            "foo:bar OR older_than:7d newer_than:12h",
        )

        assert parsed[0] == [{"kind": "text", "value": "foo:bar", "negated": False}]
        assert parsed[1][0]["kind"] == "older_than"
        assert isinstance(parsed[1][0]["value"], str)
        assert parsed[1][1]["kind"] == "newer_than"
        assert isinstance(parsed[1][1]["value"], str)
    finally:
        db.close_connection()


def test_email_like_clause_uses_backend_specific_operator() -> None:
    query_ops_module = _load_query_ops_module()

    sqlite_db = MediaDatabase(db_path=":memory:", client_id="email-query-like-sqlite-test")
    try:
        assert query_ops_module._email_like_clause(sqlite_db, "COALESCE(em.subject, '')") == (
            "COALESCE(em.subject, '') LIKE ? COLLATE NOCASE"
        )
    finally:
        sqlite_db.close_connection()

    postgres_db = SimpleNamespace(backend_type=BackendType.POSTGRESQL)
    assert query_ops_module._email_like_clause(postgres_db, "COALESCE(em.subject, '')") == (
        "COALESCE(em.subject, '') ILIKE ?"
    )


def test_search_email_messages_uses_sqlite_fts_literal_helper_and_filters_deleted_visibility(
    monkeypatch,
) -> None:
    query_ops_module = _load_query_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-query-search-test")
    try:
        live_media_id = _add_email_media(
            db,
            url="email://query-live",
            title="Query Live Email",
            content="budget marker",
        )
        db.upsert_email_message_graph(
            media_id=live_media_id,
            metadata={
                "title": "Budget Visible",
                "email": {
                    "from": "alice@example.com",
                    "to": "team@example.com",
                    "subject": "Budget Visible",
                    "date": "Mon, 10 Feb 2025 12:00:00 +0000",
                    "message_id": "<query-visible@example.com>",
                    "labels": ["Inbox"],
                },
            },
            body_text="budget marker",
            source_message_id="query-visible",
            source_key="upload:query-visible",
        )

        deleted_media_id = _add_email_media(
            db,
            url="email://query-deleted",
            title="Query Deleted Email",
            content="budget marker deleted copy",
        )
        db.upsert_email_message_graph(
            media_id=deleted_media_id,
            metadata={
                "title": "Budget Deleted",
                "email": {
                    "from": "deleted@example.com",
                    "to": "team@example.com",
                    "subject": "Budget Deleted",
                    "date": "Tue, 11 Feb 2025 12:00:00 +0000",
                    "message_id": "<query-deleted@example.com>",
                    "labels": ["Inbox"],
                },
            },
            body_text="budget marker deleted copy",
            source_message_id="query-deleted",
            source_key="upload:query-deleted",
        )
        assert db.soft_delete_media(deleted_media_id, cascade=True) is True

        fts_terms: list[str] = []
        original_literal_term = query_ops_module._sqlite_fts_literal_term

        def track_literal_term(value: str) -> str | None:
            fts_terms.append(value)
            return original_literal_term(value)

        monkeypatch.setattr(query_ops_module, "_sqlite_fts_literal_term", track_literal_term)

        rows, total = query_ops_module.search_email_messages(
            db,
            query="budget",
            include_deleted=False,
            limit=20,
            offset=0,
        )
        rows_all, total_all = query_ops_module.search_email_messages(
            db,
            query="budget",
            include_deleted=True,
            limit=20,
            offset=0,
        )

        assert "budget" in fts_terms
        assert total == 1
        assert {int(row["media_id"]) for row in rows} == {live_media_id}
        assert total_all == 2
        assert {int(row["media_id"]) for row in rows_all} == {live_media_id, deleted_media_id}
    finally:
        db.close_connection()


def test_get_email_message_detail_preserves_graph_and_include_deleted_behavior() -> None:
    query_ops_module = _load_query_ops_module()

    db = MediaDatabase(db_path=":memory:", client_id="email-query-detail-test")
    try:
        media_id = _add_email_media(
            db,
            url="email://query-detail",
            title="Query Detail Email",
            content="Detailed message body",
        )
        upsert_result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Query Detail Subject",
                "email": {
                    "from": "Alice <alice@example.com>",
                    "to": "Bob <bob@example.com>",
                    "cc": "Carol <carol@example.com>",
                    "subject": "Query Detail Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<query-detail@example.com>",
                    "attachments": [
                        {
                            "name": "detail.pdf",
                            "content_type": "application/pdf",
                            "size": 2000,
                            "content_id": "<cid-detail>",
                            "disposition": "attachment",
                        }
                    ],
                    "labels": ["Inbox", "Finance"],
                },
            },
            body_text="Detailed message body",
            source_message_id="query-detail-src",
            source_key="upload:query-detail",
        )
        email_message_id = int(upsert_result["email_message_id"])

        detail = query_ops_module.get_email_message_detail(
            db,
            email_message_id=email_message_id,
        )

        assert detail is not None
        assert int(detail["media"]["id"]) == media_id
        assert detail["participants"]["from"][0]["email"] == "alice@example.com"
        assert detail["labels"][0]["label_name"] == "Finance"
        assert detail["attachments"][0]["filename"] == "detail.pdf"

        assert db.soft_delete_media(media_id, cascade=True) is True

        assert (
            query_ops_module.get_email_message_detail(
                db,
                email_message_id=email_message_id,
            )
            is None
        )

        detail_including_deleted = query_ops_module.get_email_message_detail(
            db,
            email_message_id=email_message_id,
            include_deleted=True,
        )
        assert detail_including_deleted is not None
        assert int(detail_including_deleted["media"]["id"]) == media_id
    finally:
        db.close_connection()
