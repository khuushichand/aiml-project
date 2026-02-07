import asyncio
import sqlite3
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing import (
    persistence as ingestion_persistence,
)


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


def _patch_audio_processing(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import (
        Audio_Files as audio_files_mod,
    )

    def _fake_process_audio_files(**kwargs):
        src = kwargs["inputs"][0]
        return {
            "results": [
                {
                    "status": "Success",
                    "input_ref": src,
                    "processing_source": src,
                    "media_type": "audio",
                    "metadata": {},
                    "content": "ok",
                    "analysis_details": {},
                    "warnings": None,
                    "error": None,
                }
            ],
            "processed_count": 1,
            "errors_count": 0,
            "errors": [],
        }

    async def _fake_persist_primary_av_item(**kwargs):
        process_result = kwargs["process_result"]
        process_result["db_id"] = None
        process_result["db_message"] = "patched"
        process_result["media_uuid"] = None

    async def _fake_extract_claims_if_requested(*args, **kwargs):
        return None

    monkeypatch.setattr(
        audio_files_mod,
        "process_audio_files",
        _fake_process_audio_files,
        raising=True,
    )
    monkeypatch.setattr(
        ingestion_persistence,
        "persist_primary_av_item",
        _fake_persist_primary_av_item,
        raising=True,
    )
    monkeypatch.setattr(
        ingestion_persistence,
        "extract_claims_if_requested",
        _fake_extract_claims_if_requested,
        raising=True,
    )


@pytest.mark.asyncio
async def test_process_batch_media_non_hash_precheck_ignores_soft_deleted_rows(
    monkeypatch,
    tmp_path,
):
    source = "https://example.com/audio.mp3"
    _patch_audio_processing(monkeypatch)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Security.egress.evaluate_url_policy",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True, reason=None),
        raising=True,
    )

    observed = {"queries": [], "closed": 0}

    class _FakeMediaDatabase:
        def __init__(self, *args, **kwargs):
            pass

        def execute_query(self, query, params):
            observed["queries"].append(query)
            if "deleted = 0" in query.lower():
                # Simulate a DB where only a soft-deleted row exists.
                return _FakeCursor(None)
            # Legacy broken query path (without deleted filter) would hit this.
            return _FakeCursor({"id": 777})

        def close_connection(self):
            observed["closed"] += 1

    monkeypatch.setattr(
        ingestion_persistence,
        "MediaDatabase",
        _FakeMediaDatabase,
        raising=True,
    )

    form_data = SimpleNamespace(overwrite_existing=False, transcription_model="whisper-test")

    results = await ingestion_persistence.process_batch_media(
        media_type="audio",
        urls=[source],
        uploaded_file_paths=[],
        source_to_ref_map={source: source},
        form_data=form_data,
        chunk_options=None,
        loop=asyncio.get_running_loop(),
        db_path="unused.db",
        client_id="test_client",
        temp_dir=tmp_path,
    )

    assert observed["queries"]
    assert any("deleted = 0" in query.lower() for query in observed["queries"])
    assert observed["closed"] >= 1
    assert len(results) == 1
    assert results[0]["status"] == "Success"


@pytest.mark.asyncio
async def test_process_batch_media_precheck_closes_db_on_query_error(
    monkeypatch,
    tmp_path,
):
    source = "https://example.com/audio.mp3"
    _patch_audio_processing(monkeypatch)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Security.egress.evaluate_url_policy",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True, reason=None),
        raising=True,
    )

    observed = {"closed": 0}

    class _FakeMediaDatabase:
        def __init__(self, *args, **kwargs):
            pass

        def execute_query(self, query, params):
            raise sqlite3.OperationalError("pre-check query failed")

        def close_connection(self):
            observed["closed"] += 1

    monkeypatch.setattr(
        ingestion_persistence,
        "MediaDatabase",
        _FakeMediaDatabase,
        raising=True,
    )

    form_data = SimpleNamespace(overwrite_existing=False, transcription_model="whisper-test")

    results = await ingestion_persistence.process_batch_media(
        media_type="audio",
        urls=[source],
        uploaded_file_paths=[],
        source_to_ref_map={source: source},
        form_data=form_data,
        chunk_options=None,
        loop=asyncio.get_running_loop(),
        db_path="unused.db",
        client_id="test_client",
        temp_dir=tmp_path,
    )

    assert observed["closed"] >= 1
    assert len(results) == 1
    assert results[0]["status"] == "Success"
