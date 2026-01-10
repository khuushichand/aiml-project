import asyncio
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import (
    persistence as ingestion_persistence,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files
from tldw_Server_API.app.core.Security import egress


@pytest.mark.asyncio
async def test_process_batch_media_blocks_unsafe_url(monkeypatch, tmp_path):
    blocked_url = "http://blocked.example"

    def fake_evaluate_url_policy(_url, **_kwargs):

        return SimpleNamespace(allowed=False, reason="blocked")

    def fake_process_audio_files(**_kwargs):

        raise AssertionError("process_audio_files should not be called for blocked URLs")

    monkeypatch.setattr(egress, "evaluate_url_policy", fake_evaluate_url_policy)
    monkeypatch.setattr(Audio_Files, "process_audio_files", fake_process_audio_files)

    form_data = SimpleNamespace(overwrite_existing=True, transcription_model=None)

    results = await ingestion_persistence.process_batch_media(
        media_type="audio",
        urls=[blocked_url],
        uploaded_file_paths=[],
        source_to_ref_map={blocked_url: blocked_url},
        form_data=form_data,
        chunk_options=None,
        loop=asyncio.get_running_loop(),
        db_path=":memory:",
        client_id="test",
        temp_dir=tmp_path,
    )

    assert len(results) == 1
    assert results[0]["status"] == "Error"
    assert "URL blocked" in (results[0].get("error") or "")
