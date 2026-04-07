import json
import uuid

from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.DB_Management.media_db.legacy_transcripts import (
    upsert_transcript,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
    to_normalized_stt_artifact,
)


def _insert_minimal_media(db: MediaDatabase) -> int:
    """Insert the smallest Media row needed for transcript writes."""
    now = db._get_current_utc_timestamp_str()
    media_uuid = str(uuid.uuid4())
    sql = (
        "INSERT INTO Media (url, title, type, content, content_hash, is_trash, chunking_status, "
        "vector_processing, uuid, last_modified, version, client_id, deleted) "
        "VALUES (?, ?, ?, ?, ?, 0, 'pending', 0, ?, ?, 1, ?, 0)"
    )
    with db.transaction() as conn:
        cur = db._execute_with_connection(
            conn,
            sql,
            (
                f"http://example.com/{media_uuid}",
                "Normalized Artifact Media",
                "audio",
                "content",
                media_uuid,
                media_uuid,
                now,
                db.client_id,
            ),
        )
        return int(cur.lastrowid or 0)


def test_upsert_transcript_persists_normalized_artifact_roundtrip(tmp_path):

    db = MediaDatabase(db_path=str(tmp_path / "media.db"), client_id="normalized-test")
    media_id = _insert_minimal_media(db)

    artifact = to_normalized_stt_artifact(
        "hello world",
        [{"start": 0.0, "end": 1.0, "speaker": None, "confidence": 0.9, "text": "hello"}],
        language="en",
        provider="faster-whisper",
        model="tiny",
        duration_seconds=1.0,
        diarization_enabled=False,
    )

    payload = upsert_transcript(db, media_id, transcription=json.dumps(artifact), whisper_model="tiny")
    assert payload["media_id"] == media_id

    row = db.execute_query(
        "SELECT transcription FROM Transcripts WHERE media_id = ? AND whisper_model = ?",
        (media_id, "tiny"),
    ).fetchone()
    assert row is not None

    stored = json.loads(row["transcription"]) if isinstance(row["transcription"], str) else row["transcription"]
    # Core normalized fields should round-trip without loss
    assert stored == artifact

    db.close_connection()
