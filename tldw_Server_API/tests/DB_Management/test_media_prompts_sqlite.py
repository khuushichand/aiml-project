import uuid

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    MediaDatabase,
    get_media_prompts,
)


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
                "Prompt Test Media",
                "article",
                "lorem ipsum",
                media_uuid,
                media_uuid,
                now,
                db.client_id,
            ),
        )
        return int(cur.lastrowid or 0)


def test_sqlite_get_media_prompts_filters_and_orders(tmp_path):
    db = MediaDatabase(db_path=str(tmp_path / "media.db"), client_id="unit-sqlite-prompts")
    media_id = _insert_minimal_media(db)

    now = db._get_current_utc_timestamp_str()
    # Insert three versions: v1 with prompt "A", v2 with empty prompt (should be filtered), v3 with prompt "B"
    with db.transaction() as conn:
        # v1
        db._execute_with_connection(
            conn,
            (
                "INSERT INTO DocumentVersions (media_id, version_number, content, prompt, created_at, uuid, last_modified, version, client_id, deleted) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 0)"
            ),
            (
                media_id,
                1,
                "c1",
                "A",
                now,
                str(uuid.uuid4()),
                now,
                db.client_id,
            ),
        )
        # v2 (empty prompt) - should be filtered out
        db._execute_with_connection(
            conn,
            (
                "INSERT INTO DocumentVersions (media_id, version_number, content, prompt, created_at, uuid, last_modified, version, client_id, deleted) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 0)"
            ),
            (
                media_id,
                2,
                "c2",
                "",
                now,
                str(uuid.uuid4()),
                now,
                db.client_id,
            ),
        )
        # v3
        db._execute_with_connection(
            conn,
            (
                "INSERT INTO DocumentVersions (media_id, version_number, content, prompt, created_at, uuid, last_modified, version, client_id, deleted) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 0)"
            ),
            (
                media_id,
                3,
                "c3",
                "B",
                now,
                str(uuid.uuid4()),
                now,
                db.client_id,
            ),
        )

    prompts = get_media_prompts(db, media_id)
    # Expect two prompts (B from v3 first, then A from v1)
    assert [p["content"] for p in prompts] == ["B", "A"]
    assert [p["version_number"] for p in prompts] == [3, 1]
