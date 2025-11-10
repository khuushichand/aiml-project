from __future__ import annotations

import os
import uuid
import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


@pytest.mark.integration
def test_chacha_transaction_context_commits_if_available(tmp_path, pg_database_config: DatabaseConfig):
    backend = DatabaseBackendFactory.create_backend(pg_database_config)
    db = CharactersRAGDB(db_path=":memory:", client_id="txn-chacha", backend=backend)

    try:
        card_id = db.add_character_card(
            {
                "name": f"txn-char-{uuid.uuid4()}",
                "description": "transactional character",
                "client_id": db.client_id,
            }
        )
        assert card_id is not None

        conversation_id = db.add_conversation(
            {
                "character_id": card_id,
                "title": "original title",
                "client_id": db.client_id,
            }
        )
        assert conversation_id is not None

        updated_title = "updated title"
        with db.transaction():
            db.execute_query(
                "UPDATE conversations SET title = ?, version = version + 1 WHERE id = ?",
                (updated_title, conversation_id),
            )

        db.close_connection()

        fetch_cursor = db.execute_query(
            "SELECT title FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        row = fetch_cursor.fetchone()
        assert row is not None and row["title"] == updated_title  # type: ignore[index]

        failing_conversation = str(uuid.uuid4())
        with pytest.raises(RuntimeError):
            with db.transaction():
                db.execute_query(
                    "INSERT INTO conversations (id, root_id, character_id, client_id) VALUES (?, ?, ?, ?)",
                    (failing_conversation, failing_conversation, card_id, db.client_id),
                )
                raise RuntimeError("force rollback")

        db.close_connection()

        not_found_cursor = db.execute_query(
            "SELECT id FROM conversations WHERE id = ?",
            (failing_conversation,),
        )
        assert not_found_cursor.fetchone() is None
    finally:
        try:
            db.close_connection()
            if db.backend_type == BackendType.POSTGRESQL:
                db.backend.get_pool().close_all()
        except Exception:
            pass
