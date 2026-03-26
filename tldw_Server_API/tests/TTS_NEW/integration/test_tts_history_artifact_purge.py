import pytest
from fastapi import status

from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.config import settings


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_output_delete_updates_tts_history(test_client, auth_headers, monkeypatch, tmp_path):
    user_db_base = tmp_path / "user_dbs"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(user_db_base))
    monkeypatch.setattr(settings, "USER_DB_BASE_DIR", str(user_db_base), raising=False)

    cdb = CollectionsDatabase.for_user(1)
    output_row = cdb.create_output_artifact(
        type_="tts_audio",
        title="TTS Output",
        format_="mp3",
        storage_path="tts_output.mp3",
    )
    cdb.close()

    media_db = MediaDatabase(db_path=str(DatabasePaths.get_media_db_path(1)), client_id="tts_history_test")
    history_id = media_db.create_tts_history_entry(
        user_id="1",
        text_hash="hash-output",
        text="hello",
        text_length=5,
        provider="openai",
        model="tts-1",
        voice_name="alloy",
        format="mp3",
        status="success",
        output_id=output_row.id,
    )
    media_db.close_connection()

    resp = test_client.delete(f"/api/v1/outputs/{output_row.id}", headers=auth_headers)
    assert resp.status_code == status.HTTP_200_OK

    media_db = MediaDatabase(db_path=str(DatabasePaths.get_media_db_path(1)), client_id="tts_history_test_read")
    row = media_db.get_tts_history_entry(user_id="1", history_id=history_id, include_deleted=True)
    media_db.close_connection()

    assert row is not None
    assert row["artifact_deleted_at"] is not None
    assert row["output_id"] is None
