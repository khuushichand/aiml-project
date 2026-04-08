from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.dedupe_urls import (
    normalize_media_dedupe_url,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing import (
    persistence as ingestion_persistence,
)


@pytest.mark.asyncio
async def test_process_batch_media_precheck_skips_normalized_url_variants(
    media_database,
    monkeypatch,
    tmp_path,
) -> None:
    source_variant = "HTTPS://Example.com/audio.mp3/?utm_source=beta&b=2&a=1#frag"
    canonical_url = normalize_media_dedupe_url(source_variant)
    assert canonical_url == "https://example.com/audio.mp3?a=1&b=2"

    existing_id, _, _ = media_database.add_media_with_keywords(
        url=canonical_url,
        title="Existing Audio",
        media_type="audio",
        content="existing transcription",
        transcription_model="whisper-test",
        keywords=None,
    )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Security.egress.evaluate_url_policy",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True, reason=None),
        raising=True,
    )

    form_data = SimpleNamespace(overwrite_existing=False, transcription_model="whisper-test")

    results = await ingestion_persistence.process_batch_media(
        media_type="audio",
        urls=[source_variant],
        uploaded_file_paths=[],
        source_to_ref_map={source_variant: source_variant},
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


@pytest.mark.asyncio
async def test_process_batch_media_precheck_skips_existing_url_even_without_model_match(
    media_database,
    monkeypatch,
    tmp_path,
) -> None:
    source_url = "https://example.com/audio.mp3?b=2&a=1"
    canonical_url = normalize_media_dedupe_url(source_url)
    assert canonical_url == "https://example.com/audio.mp3?a=1&b=2"

    existing_id, _, _ = media_database.add_media_with_keywords(
        url=canonical_url,
        title="Existing Audio",
        media_type="audio",
        content="existing transcription",
        transcription_model=None,
        keywords=None,
    )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Security.egress.evaluate_url_policy",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True, reason=None),
        raising=True,
    )

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import (
        Audio_Files as audio_files_mod,
    )

    def _boom(**_kwargs):
        raise AssertionError("audio processor should not run when existing media is reused")

    monkeypatch.setattr(
        audio_files_mod,
        "process_audio_files",
        _boom,
        raising=True,
    )

    form_data = SimpleNamespace(overwrite_existing=False, transcription_model="whisper-test")

    results = await ingestion_persistence.process_batch_media(
        media_type="audio",
        urls=[source_url],
        uploaded_file_paths=[],
        source_to_ref_map={source_url: source_url},
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
