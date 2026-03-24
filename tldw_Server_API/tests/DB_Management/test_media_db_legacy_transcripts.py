from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.DB_Management.media_db.legacy_transcripts import (
    soft_delete_transcript,
    upsert_transcript,
)
from tldw_Server_API.app.core.DB_Management.media_db.repositories.media_repository import (
    MediaRepository,
)


def test_legacy_transcript_helpers_round_trip_update_and_soft_delete() -> None:
    db = MediaDatabase(db_path=":memory:", client_id="legacy-transcript-helpers")
    media_repo = MediaRepository.from_legacy_db(db)
    try:
        media_id, _media_uuid, _msg = media_repo.add_text_media(
            title="Transcripted doc",
            content="spoken words",
            media_type="audio",
        )

        created = upsert_transcript(
            db,
            media_id=media_id,
            transcription='{"text": "first"}',
            whisper_model="base",
        )
        updated = upsert_transcript(
            db,
            media_id=media_id,
            transcription='{"text": "second"}',
            whisper_model="base",
        )

        deleted = soft_delete_transcript(db, updated["uuid"])

        transcript_row = db.execute_query(
            "SELECT deleted, version, client_id, transcription FROM Transcripts WHERE uuid = ?",
            (updated["uuid"],),
        ).fetchone()
        sync_row = db.execute_query(
            """
            SELECT entity, operation, version, client_id
            FROM sync_log
            WHERE entity_uuid = ?
            ORDER BY change_id DESC
            LIMIT 1
            """,
            (updated["uuid"],),
        ).fetchone()

        assert updated["uuid"] == created["uuid"]
        assert updated["version"] == created["version"] + 1
        assert deleted is True
        assert transcript_row is not None
        assert transcript_row["deleted"] == 1
        assert transcript_row["version"] == updated["version"] + 1
        assert transcript_row["client_id"] == "legacy-transcript-helpers"
        assert "second" in transcript_row["transcription"]
        assert sync_row is not None
        assert sync_row["entity"] == "Transcripts"
        assert sync_row["operation"] == "delete"
        assert sync_row["version"] == transcript_row["version"]
        assert sync_row["client_id"] == "legacy-transcript-helpers"
    finally:
        db.close_connection()
