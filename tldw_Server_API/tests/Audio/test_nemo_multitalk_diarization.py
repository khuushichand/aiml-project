import json

import pytest


def test_multitalk_segment_mapping():
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Diarization_Nemo_Multitalk as nemo_mt

    raw_segments = [
        {"speaker": "speaker_0", "start_time": 0.0, "end_time": 1.0, "words": "hello"},
        {"speaker": "speaker_1", "start_time": 1.0, "end_time": 2.0, "words": "world"},
    ]

    normalized = nemo_mt.normalize_multitalk_segments(raw_segments, audio_duration=2.0)

    assert normalized[0]["Text"] == "hello"
    assert normalized[0]["start_seconds"] == pytest.approx(0.0)
    assert normalized[0]["end_seconds"] == pytest.approx(1.0)
    assert normalized[1]["speaker_id"] == 1
    assert normalized[1]["speaker_label"] == "SPEAKER_1"


def test_multitalk_word_list_normalization():
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Diarization_Nemo_Multitalk as nemo_mt

    raw_segments = [
        {
            "speaker": "speaker_0",
            "start_time": 0.0,
            "end_time": 1.0,
            "words": [{"word": "hello"}, {"word": "world"}],
        }
    ]

    normalized = nemo_mt.normalize_multitalk_segments(raw_segments, audio_duration=1.0)
    assert normalized[0]["Text"] == "hello world"


def test_perform_transcription_prefers_nemo_multitalk(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Transcription_Lib as atl
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Diarization_Nemo_Multitalk as nemo_mt

    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"RIFF0000")

    monkeypatch.setattr(atl, "convert_to_wav", lambda *args, **kwargs: str(audio_path))
    monkeypatch.setattr(atl, "_assert_no_symlink", lambda *args, **kwargs: None)
    monkeypatch.setattr(atl, "_resolve_transcript_cache_dir", lambda *args, **kwargs: tmp_path)

    def _should_not_run(*args, **kwargs):
        raise AssertionError("run_stt_batch_via_registry should not be called")

    monkeypatch.setattr(atl, "run_stt_batch_via_registry", _should_not_run)

    def _fake_multitalk(audio_path, config, output_path=None):
        return {
            "segments": [
                {
                    "start_seconds": 0.0,
                    "end_seconds": 1.0,
                    "start": 0.0,
                    "end": 1.0,
                    "Text": "hi",
                    "speaker_id": 0,
                    "speaker_label": "SPEAKER_0",
                }
            ],
            "speakers": [],
            "duration": 1.0,
            "num_speakers": 1,
        }

    monkeypatch.setattr(nemo_mt, "transcribe_with_nemo_multitalk", _fake_multitalk)
    monkeypatch.setattr(atl, "load_diarization_config", lambda: {"backend": "nemo_multitalk"})

    audio_file, segments = atl.perform_transcription(
        video_path=str(audio_path),
        offset=0,
        transcription_model="parakeet",
        vad_use=False,
        diarize=True,
        overwrite=True,
        transcription_language="en",
    )

    assert audio_file == str(audio_path)
    assert segments and segments[0]["Text"] == "hi"

    diarized_cache = tmp_path / "input-transcription_model-parakeet.diarized.json"
    assert diarized_cache.exists()
    payload = json.loads(diarized_cache.read_text())
    assert payload["segments"][0]["speaker_label"] == "SPEAKER_0"


def test_perform_transcription_rejects_non_nemo_variant(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Transcription_Lib as atl
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Diarization_Nemo_Multitalk as nemo_mt

    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"RIFF0000")

    monkeypatch.setattr(atl, "convert_to_wav", lambda *args, **kwargs: str(audio_path))
    monkeypatch.setattr(atl, "_assert_no_symlink", lambda *args, **kwargs: None)
    monkeypatch.setattr(atl, "_resolve_transcript_cache_dir", lambda *args, **kwargs: tmp_path)
    monkeypatch.setattr(atl, "load_diarization_config", lambda: {"backend": "nemo_multitalk"})

    monkeypatch.setattr(nemo_mt, "transcribe_with_nemo_multitalk", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("multitalk should not run")))

    class _NoDiarizationService:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Embedding diarization should not run")

    monkeypatch.setattr(atl, "DiarizationService", _NoDiarizationService)

    called = {"stt": False}

    def _fake_run_stt(*args, **kwargs):
        called["stt"] = True
        return {"segments": [{"start_seconds": 0.0, "end_seconds": 1.0, "Text": "hi"}]}

    monkeypatch.setattr(atl, "run_stt_batch_via_registry", _fake_run_stt)

    audio_file, segments = atl.perform_transcription(
        video_path=str(audio_path),
        offset=0,
        transcription_model="parakeet-mlx",
        vad_use=False,
        diarize=True,
        overwrite=True,
        transcription_language="en",
    )

    assert called["stt"] is True
    assert audio_file == str(audio_path)
    assert segments and segments[0]["Text"] == "hi"
