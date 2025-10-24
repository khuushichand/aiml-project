import os
import sqlite3
import tempfile
import types
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    MediaDatabase,
    fetch_keywords_for_media,
    get_document_version,
    create_automated_backup,
    create_incremental_backup,
    rotate_backups,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Media_Update_lib import (
    process_media_update,
)


def _make_media_db() -> MediaDatabase:
    return MediaDatabase(db_path=":memory:", client_id="tests-db")


def test_batch_insert_chunks_generates_unique_ids_across_calls():
    db = _make_media_db()
    media_id, _, _ = db.add_media_with_keywords(
        title="Chunked Doc",
        media_type="text",
        content="chunk source",
        keywords=[],
    )

    first_batch = [
        {'text': "chunk-1", 'metadata': {'start_index': 0, 'end_index': 5}},
        {'text': "chunk-2", 'metadata': {'start_index': 6, 'end_index': 11}},
    ]
    second_batch = [
        {'text': "chunk-3", 'metadata': {'start_index': 12, 'end_index': 18}},
        {'text': "chunk-4", 'metadata': {'start_index': 19, 'end_index': 25}},
    ]

    inserted_first = db.batch_insert_chunks(media_id, first_batch)
    assert inserted_first == len(first_batch)

    inserted_second = db.batch_insert_chunks(media_id, second_batch)
    assert inserted_second == len(second_batch)

    with db.transaction() as conn:
        cursor = conn.execute("SELECT chunk_id FROM MediaChunks WHERE media_id = ?", (media_id,))
        rows = cursor.fetchall()

    chunk_ids = [row['chunk_id'] for row in rows]
    assert len(chunk_ids) == len(first_batch) + len(second_batch)
    assert len(set(chunk_ids)) == len(chunk_ids), "chunk_id values should be unique across batches"


def test_soft_delete_keyword_uses_execute_with_connection(monkeypatch):
    db = _make_media_db()
    db.add_keyword("alpha")

    executed: list[str] = []
    original = db._execute_with_connection

    def spy(self, conn, query, params=None):
        executed.append(query)
        return original(conn, query, params)

    db._execute_with_connection = types.MethodType(spy, db)
    assert db.soft_delete_keyword("alpha") is True
    assert any("FROM Keywords" in q for q in executed)


def test_soft_delete_document_version_uses_execute_with_connection(monkeypatch):
    db = _make_media_db()
    media_id, _, _ = db.add_media_with_keywords(
        title="Doc",
        media_type="text",
        content="version-1",
        keywords=["tag1"],
    )
    db.create_document_version(media_id=media_id, content="version-2")
    target = get_document_version(db, media_id=media_id, version_number=2, include_content=False)
    assert target and target["uuid"]

    executed: list[str] = []
    original = db._execute_with_connection

    def spy(self, conn, query, params=None):
        executed.append(query)
        return original(conn, query, params)

    db._execute_with_connection = types.MethodType(spy, db)
    assert db.soft_delete_document_version(target["uuid"]) is True
    assert any("DocumentVersions" in q for q in executed)


def test_process_media_update_wraps_transaction_and_commits():
    db = _make_media_db()
    media_id, _, _ = db.add_media_with_keywords(
        title="Doc",
        media_type="text",
        content="original content",
        keywords=["old"],
    )

    enter_count = 0
    original_transaction = db.transaction

    def tracking_transaction(self):
        nonlocal enter_count
        enter_count += 1
        return original_transaction()

    db.transaction = types.MethodType(tracking_transaction, db)

    keywords = ["new1", "new2"]
    result = process_media_update(
        db,
        media_id=media_id,
        content="updated content",
        prompt="p2",
        summary="s2",
        keywords=keywords,
    )

    assert result["status"] == "Success"
    expected_transactions = 1 + len(set(keywords))  # outer + add_keyword per new keyword
    assert enter_count == expected_transactions

    latest = get_document_version(db, media_id=media_id, version_number=None, include_content=True)
    assert latest and latest["content"] == "updated content"
    assert latest["prompt"] == "p2"
    assert latest["analysis_content"] == "s2"

    tags = fetch_keywords_for_media(media_id=media_id, db_instance=db)
    assert set(tags) == {"new1", "new2"}


def test_media_db_backup_helpers_create_and_rotate(tmp_path: Path):
    db_path = tmp_path / "media.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO sample (value) VALUES ('row')")
    conn.commit()
    conn.close()

    backup_dir = tmp_path / "backups"
    msg = create_automated_backup(str(db_path), str(backup_dir))
    assert "Backup created" in msg
    backups = list(backup_dir.glob("*.db"))
    assert backups

    msg_inc = create_incremental_backup(str(db_path), str(backup_dir))
    assert "Incremental backup created" in msg_inc
    incremental = list(backup_dir.glob("*.sqlib"))
    assert incremental

    # Create extra backups to trigger rotation
    for idx in range(5):
        (backup_dir / f"old_{idx}.db").touch()

    rotate_msg = rotate_backups(str(backup_dir), max_backups=3)
    assert "Removed" in rotate_msg or rotate_msg == "No rotation needed."
    remaining = [
        f for f in os.listdir(backup_dir) if f.endswith((".db", ".sqlib"))
    ]
    assert len(remaining) <= 3
