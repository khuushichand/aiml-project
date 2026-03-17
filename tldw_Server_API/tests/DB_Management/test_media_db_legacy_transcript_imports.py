import importlib

from tldw_Server_API.app.core.DB_Management.media_db import legacy_transcripts


def test_media_db_v2_no_longer_reexports_transcript_helpers() -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )

    assert not hasattr(media_db_v2, "upsert_transcript")
    assert not hasattr(media_db_v2, "soft_delete_transcript")


def test_audio_streaming_imports_upsert_transcript_from_legacy_transcripts(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    audio_streaming = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.audio.audio_streaming"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError(
            "audio_streaming should not bind upsert_transcript from Media_DB_v2"
        )

    monkeypatch.setattr(
        media_db_v2,
        "upsert_transcript",
        _shim_should_not_be_bound,
        raising=False,
    )

    reloaded = importlib.reload(audio_streaming)
    assert reloaded.upsert_transcript is legacy_transcripts.upsert_transcript
