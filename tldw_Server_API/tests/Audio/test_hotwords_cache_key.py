from __future__ import annotations

import pytest


@pytest.mark.unit
def test_perform_transcription_hotwords_cache_key_isolated(monkeypatch, tmp_path):
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as atlib

    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"\x00\x00")

    calls = {"count": 0}

    def _fake_convert_to_wav(*_args, **_kwargs):
        return str(wav_path)

    def _fake_run_stt_batch_via_registry(
        audio_file_path,
        transcription_model,
        *,
        vad_filter=False,
        selected_source_lang="en",
        hotwords=None,
        duration_seconds=None,
        base_dir=None,
        cancel_check=None,
    ):
        calls["count"] += 1
        label = " ".join(hotwords) if isinstance(hotwords, (list, tuple)) else str(hotwords or "")
        segs = [{"Text": f"segment:{label or 'none'}", "start_seconds": 0.0, "end_seconds": 1.0}]
        return {
            "text": segs[0]["Text"],
            "language": selected_source_lang,
            "segments": segs,
            "diarization": {"enabled": False, "speakers": None},
            "usage": {"duration_ms": None, "tokens": None},
            "metadata": {"provider": "vibevoice", "model": transcription_model},
        }

    monkeypatch.setattr(atlib, "convert_to_wav", _fake_convert_to_wav, raising=True)
    monkeypatch.setattr(atlib, "run_stt_batch_via_registry", _fake_run_stt_batch_via_registry, raising=True)

    # First hotword set: compute and cache.
    _, segs_alpha = atlib.perform_transcription(
        str(wav_path),
        offset=0,
        transcription_model="vibevoice-asr",
        vad_use=False,
        transcription_language="en",
        hotwords="alpha",
        temp_dir=str(tmp_path),
    )
    assert calls["count"] == 1
    assert segs_alpha and "alpha" in segs_alpha[0]["Text"]

    # Different hotwords must not reuse the cached alpha transcript.
    _, segs_beta = atlib.perform_transcription(
        str(wav_path),
        offset=0,
        transcription_model="vibevoice-asr",
        vad_use=False,
        transcription_language="en",
        hotwords="beta",
        temp_dir=str(tmp_path),
    )
    assert calls["count"] == 2
    assert segs_beta and "beta" in segs_beta[0]["Text"]

    # Repeating the original hotwords should hit the cache.
    _, segs_alpha_cached = atlib.perform_transcription(
        str(wav_path),
        offset=0,
        transcription_model="vibevoice-asr",
        vad_use=False,
        transcription_language="en",
        hotwords="alpha",
        temp_dir=str(tmp_path),
    )
    assert calls["count"] == 2
    assert segs_alpha_cached == segs_alpha

