import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import (
    persistence as ingestion_persistence,
)


@pytest.mark.asyncio
async def test_process_batch_media_falls_back_to_safe_metadata_when_source_hash_missing(
    media_database,
    tmp_path,
):
    test_path = tmp_path / "dup_audio.wav"
    payload = b"duplicate audio content"
    test_path.write_bytes(payload)
    source_hash = hashlib.sha256(payload).hexdigest()
    safe_metadata = json.dumps({"source_hash": source_hash}, separators=(",", ":"))
    url = str(test_path)

    existing_id, _, _ = media_database.add_media_with_keywords(
        url=url,
        title="Existing Audio",
        media_type="audio",
        content="existing content",
        transcription_model="whisper-test",
        safe_metadata=safe_metadata,
        keywords=None,
    )

    cursor = media_database.execute_query(
        "SELECT source_hash FROM Media WHERE id = ?",
        (existing_id,),
    )
    row = cursor.fetchone()
    assert row["source_hash"] is None

    form_data = SimpleNamespace(overwrite_existing=False, transcription_model="whisper-test")

    results = await ingestion_persistence.process_batch_media(
        media_type="audio",
        urls=[],
        uploaded_file_paths=[url],
        source_to_ref_map={url: url},
        form_data=form_data,
        chunk_options=None,
        loop=asyncio.get_running_loop(),
        db_path=media_database.db_path_str,
        client_id="test_client",
        temp_dir=tmp_path,
    )

    assert len(results) == 1
    assert results[0]["status"] == "Skipped"
    assert results[0]["db_id"] == existing_id
