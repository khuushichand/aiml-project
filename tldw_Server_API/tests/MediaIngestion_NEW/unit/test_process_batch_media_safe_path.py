import asyncio
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import (
    persistence as ingestion_persistence,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files


@pytest.mark.asyncio
async def test_process_batch_media_warns_on_unsafe_path(monkeypatch, tmp_path):
    unsafe_path = "../escape.txt"

    def fake_process_audio_files(**kwargs):

             inputs = kwargs.get("inputs", [])
        return {
            "results": [
                {
                    "status": "Success",
                    "input_ref": inputs[0] if inputs else "Unknown",
                    "processing_source": inputs[0] if inputs else "Unknown",
                    "metadata": {},
                    "content": None,
                    "transcript": None,
                    "segments": None,
                    "chunks": None,
                    "analysis": None,
                    "summary": None,
                    "analysis_details": None,
                    "error": None,
                    "warnings": None,
                    "db_id": None,
                    "db_message": None,
                }
            ]
        }

    async def fake_persist_primary_av_item(**_kwargs):
        return None

    async def fake_extract_claims_if_requested(*_args, **_kwargs):
        return None

    monkeypatch.setattr(Audio_Files, "process_audio_files", fake_process_audio_files)
    monkeypatch.setattr(
        ingestion_persistence,
        "persist_primary_av_item",
        fake_persist_primary_av_item,
    )
    monkeypatch.setattr(
        ingestion_persistence,
        "extract_claims_if_requested",
        fake_extract_claims_if_requested,
    )

    form_data = SimpleNamespace(overwrite_existing=True, transcription_model=None)

    results = await ingestion_persistence.process_batch_media(
        media_type="audio",
        urls=[],
        uploaded_file_paths=[unsafe_path],
        source_to_ref_map={unsafe_path: "escape.txt"},
        form_data=form_data,
        chunk_options=None,
        loop=asyncio.get_running_loop(),
        db_path=":memory:",
        client_id="test",
        temp_dir=tmp_path,
    )

    assert len(results) == 1
    warnings = results[0].get("warnings") or []
    assert any("Source hash skipped" in warning for warning in warnings)
