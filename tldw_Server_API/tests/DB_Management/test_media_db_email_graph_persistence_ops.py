from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.scope_context import scoped_context


pytestmark = pytest.mark.unit
def _add_email_media(
    db: MediaDatabase,
    *,
    url: str,
    title: str,
    content: str,
) -> int:
    media_id, _media_uuid, _msg = db.add_media_with_keywords(
        url=url,
        title=title,
        media_type="email",
        content=content,
        keywords=["email"],
        author="tester@example.com",
    )
    assert media_id is not None
    return int(media_id)


def test_resolve_email_tenant_id_prefers_explicit_tenant_id() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="client-scope")
    try:
        with scoped_context(user_id=42, org_ids=[84], active_org_id=99):
            assert db._resolve_email_tenant_id("tenant:explicit") == "tenant:explicit"
    finally:
        db.close_connection()


def test_resolve_email_tenant_id_uses_scope_then_client_fallback() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="client-scope")
    try:
        with scoped_context(user_id=42, org_ids=[84], active_org_id=99):
            assert db._resolve_email_tenant_id(None) == "org:99"
        with scoped_context(user_id=42):
            assert db._resolve_email_tenant_id(None) == "user:42"
        assert db._resolve_email_tenant_id(None) == "client-scope"
    finally:
        db.close_connection()


def test_upsert_email_message_graph_helper_creates_graph_and_sqlite_fts() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-graph-helper-create")
    try:
        media_id = _add_email_media(
            db,
            url="email://graph-create-1",
            title="Graph Create Email",
            content="Graph create body",
        )

        result = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Graph Create Subject",
                "email": {
                    "from": "Alice <alice@example.com>",
                    "to": "Bob <bob@example.com>",
                    "cc": "Team <team@example.com>",
                    "subject": "Graph Create Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<graph-create@example.com>",
                    "attachments": [
                        {
                            "name": "graph.pdf",
                            "content_type": "application/pdf",
                            "size": 1234,
                            "content_id": "<cid-1>",
                        }
                    ],
                    "labels": ["INBOX", "STARRED"],
                },
            },
            body_text="Graph create body",
            tenant_id="user:42",
            provider="gmail",
            source_key="gmail-graph-create",
            source_message_id="gmail-graph-create-1",
            labels=["UNREAD"],
        )

        message_id = int(result["email_message_id"])
        source_row = db.execute_query(
            "SELECT id FROM email_sources WHERE tenant_id = ? AND provider = ? AND source_key = ?",
            ("user:42", "gmail", "gmail-graph-create"),
        ).fetchone()
        message_row = db.execute_query(
            "SELECT subject, message_id, label_text, has_attachments FROM email_messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        participant_count = db.execute_query(
            "SELECT COUNT(*) AS total FROM email_message_participants WHERE email_message_id = ?",
            (message_id,),
        ).fetchone()
        attachment_count = db.execute_query(
            "SELECT COUNT(*) AS total FROM email_attachments WHERE email_message_id = ?",
            (message_id,),
        ).fetchone()
        fts_row = db.execute_query(
            "SELECT subject, label_text FROM email_fts WHERE rowid = ?",
            (message_id,),
        ).fetchone()

        assert source_row is not None
        assert result["tenant_id"] == "user:42"
        assert result["match_strategy"] == "new"
        assert message_row is not None
        assert message_row["subject"] == "Graph Create Subject"
        assert message_row["message_id"] == "<graph-create@example.com>"
        assert message_row["label_text"] == "UNREAD, INBOX, STARRED"
        assert int(message_row["has_attachments"]) == 1
        assert participant_count is not None
        assert int(participant_count["total"]) == 3
        assert attachment_count is not None
        assert int(attachment_count["total"]) == 1
        assert fts_row is not None
        assert fts_row["subject"] == "Graph Create Subject"
        assert fts_row["label_text"] == "UNREAD, INBOX, STARRED"
    finally:
        db.close_connection()


def test_upsert_email_message_graph_helper_reuses_source_message_and_refreshes_children() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="email-graph-helper-refresh")
    try:
        media_id = _add_email_media(
            db,
            url="email://graph-refresh-1",
            title="Graph Refresh Email",
            content="Graph refresh body",
        )

        first = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Graph Refresh Subject",
                "email": {
                    "from": "alice@example.com",
                    "to": "bob@example.com",
                    "subject": "Graph Refresh Subject",
                    "date": "Fri, 10 Jan 2025 09:00:00 +0000",
                    "message_id": "<graph-refresh@example.com>",
                    "attachments": [{"name": "old.pdf", "size": 100}],
                    "labels": ["INBOX", "UNREAD"],
                },
            },
            body_text="Original graph body",
            tenant_id="user:42",
            provider="gmail",
            source_key="gmail-graph-refresh",
            source_message_id="gmail-graph-refresh-1",
        )
        second = db.upsert_email_message_graph(
            media_id=media_id,
            metadata={
                "title": "Graph Refresh Subject Updated",
                "email": {
                    "from": "alice@example.com",
                    "to": "carol@example.com",
                    "subject": "Graph Refresh Subject Updated",
                    "date": "Fri, 10 Jan 2025 10:00:00 +0000",
                    "message_id": "<graph-refresh-updated@example.com>",
                    "attachments": [],
                    "labels": ["STARRED"],
                },
            },
            body_text="Updated graph body",
            tenant_id="user:42",
            provider="gmail",
            source_key="gmail-graph-refresh",
            source_message_id="gmail-graph-refresh-1",
        )

        message_id = int(second["email_message_id"])
        label_rows = db.execute_query(
            (
                "SELECT el.label_name "
                "FROM email_message_labels eml "
                "JOIN email_labels el ON el.id = eml.label_id "
                "WHERE eml.email_message_id = ? "
                "ORDER BY el.label_name ASC"
            ),
            (message_id,),
        ).fetchall()
        attachment_count = db.execute_query(
            "SELECT COUNT(*) AS total FROM email_attachments WHERE email_message_id = ?",
            (message_id,),
        ).fetchone()
        participant_rows = db.execute_query(
            (
                "SELECT emp.role, ep.email_normalized "
                "FROM email_message_participants emp "
                "JOIN email_participants ep ON ep.id = emp.participant_id "
                "WHERE emp.email_message_id = ? "
                "ORDER BY emp.role ASC, ep.email_normalized ASC"
            ),
            (message_id,),
        ).fetchall()
        fts_row = db.execute_query(
            "SELECT subject, body_text, label_text FROM email_fts WHERE rowid = ?",
            (message_id,),
        ).fetchone()

        assert int(first["email_message_id"]) == message_id
        assert second["match_strategy"] == "source_message_id"
        assert [str(row["label_name"]) for row in label_rows] == ["STARRED"]
        assert attachment_count is not None
        assert int(attachment_count["total"]) == 0
        assert [(row["role"], row["email_normalized"]) for row in participant_rows] == [
            ("from", "alice@example.com"),
            ("to", "carol@example.com"),
        ]
        assert fts_row is not None
        assert fts_row["subject"] == "Graph Refresh Subject Updated"
        assert fts_row["body_text"] == "Updated graph body"
        assert fts_row["label_text"] == "STARRED"
    finally:
        db.close_connection()
