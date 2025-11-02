import os
import uuid
import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase, upsert_transcript
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


def _insert_minimal_media(db: MediaDatabase) -> int:
    now = db._get_current_utc_timestamp_str()
    media_uuid = str(uuid.uuid4())
    sql = (
        "INSERT INTO Media (url, title, type, content, content_hash, is_trash, chunking_status, vector_processing, uuid, last_modified, version, client_id, deleted) "
        "VALUES (?, ?, ?, ?, ?, 0, 'pending', 0, ?, ?, 1, ?, 0)"
    )
    with db.transaction() as conn:
        cur = db._execute_with_connection(
            conn,
            sql,
            (
                f"http://example.com/{media_uuid}",
                "Unit Test Media",
                "article",
                "lorem ipsum",
                media_uuid,
                media_uuid,
                now,
                db.client_id,
            ),
        )
        if db.backend_type == BackendType.POSTGRESQL:
            # No RETURNING clause, fetch id
            row = db._fetchone_with_connection(conn, "SELECT id FROM Media WHERE uuid = ?", (media_uuid,))
            return int(row["id"])  # type: ignore[index]
        return int(cur.lastrowid or 0)


def test_sqlite_upsert_transcript_roundtrip(tmp_path):
    db = MediaDatabase(db_path=str(tmp_path / "media.db"), client_id="unit-sqlite")
    media_id = _insert_minimal_media(db)

    # Insert new transcript
    p1 = upsert_transcript(db, media_id, transcription="hello world", whisper_model="base")
    assert p1["media_id"] == media_id and p1["version"] >= 1 and p1["uuid"]

    # Update same transcript (same whisper_model), verify version bump
    p2 = upsert_transcript(db, media_id, transcription="updated text", whisper_model="base")
    assert p2["version"] == p1["version"] + 1

    # Latest transcription should be updated
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import get_latest_transcription
    latest = get_latest_transcription(db, media_id)
    assert latest == "updated text"


@pytest.mark.integration
def test_postgres_upsert_transcript_roundtrip_if_available(tmp_path, pg_eval_params):
    cfg = DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=pg_eval_params["host"],
        pg_port=int(pg_eval_params["port"]),
        pg_database=pg_eval_params["database"],
        pg_user=pg_eval_params["user"],
        pg_password=pg_eval_params.get("password"),
    )
    try:
        backend = DatabaseBackendFactory.create_backend(cfg)
    except Exception:
        pytest.skip("psycopg backend not available")

    db = MediaDatabase(db_path=":memory:", client_id="unit-pg", backend=backend)
    media_id = _insert_minimal_media(db)

    p1 = upsert_transcript(db, media_id, transcription="pg hello", whisper_model="large-v3")
    assert p1["media_id"] == media_id and p1["version"] >= 1 and p1["uuid"]

    p2 = upsert_transcript(db, media_id, transcription="pg updated", whisper_model="large-v3")
    assert p2["version"] == p1["version"] + 1

    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import get_latest_transcription
    latest = get_latest_transcription(db, media_id)
    assert latest == "pg updated"


@pytest.mark.integration
def test_postgres_transaction_context_commits_if_available(tmp_path, pg_eval_params):
    cfg = DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=pg_eval_params["host"],
        pg_port=int(pg_eval_params["port"]),
        pg_database=pg_eval_params["database"],
        pg_user=pg_eval_params["user"],
        pg_password=pg_eval_params.get("password"),
    )
    try:
        backend = DatabaseBackendFactory.create_backend(cfg)
    except Exception:
        pytest.skip("psycopg backend not available")

    db = MediaDatabase(db_path=":memory:", client_id="txn-pg", backend=backend)

    inserted_uuid = str(uuid.uuid4())
    timestamp = db._get_current_utc_timestamp_str()
    insert_sql = (
        "INSERT INTO Media (url, title, type, content, content_hash, is_trash, chunking_status, "
        "vector_processing, uuid, last_modified, version, client_id, deleted) "
        "VALUES (?, ?, ?, ?, ?, 0, 'pending', 0, ?, ?, 1, ?, 0)"
    )

    with db.transaction() as conn:
        db._execute_with_connection(
            conn,
            insert_sql,
            (
                f"http://example.com/{inserted_uuid}",
                "Txn Commit Media",
                "article",
                "content",
                inserted_uuid,
                inserted_uuid,
                timestamp,
                db.client_id,
            ),
        )

    db.close_connection()

    with db.transaction() as conn:
        row = db._fetchone_with_connection(
            conn,
            "SELECT uuid FROM Media WHERE uuid = ?",
            (inserted_uuid,),
        )
        assert row is not None and row["uuid"] == inserted_uuid  # type: ignore[index]
        db._execute_with_connection(conn, "DELETE FROM Media WHERE uuid = ?", (inserted_uuid,))

    db.close_connection()

    failed_uuid = str(uuid.uuid4())
    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            db._execute_with_connection(
                conn,
                insert_sql,
                (
                    f"http://example.com/{failed_uuid}",
                    "Txn Rollback Media",
                    "article",
                    "content",
                    failed_uuid,
                    failed_uuid,
                    timestamp,
                    db.client_id,
                ),
            )
            raise RuntimeError("force rollback")

    db.close_connection()

    with db.transaction() as conn:
        row = db._fetchone_with_connection(
            conn,
            "SELECT uuid FROM Media WHERE uuid = ?",
            (failed_uuid,),
        )
        assert row is None
