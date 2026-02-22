import wave

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files as audio_files


@pytest.mark.unit
def test_process_audio_files_uses_check_transcription_model_status(monkeypatch, tmp_path):
    """process_audio_files should consult check_transcription_model_status and surface warnings."""
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"\x00" * 2048)

    # Stub speech_to_text so no real STT runs
    def fake_speech_to_text(audio_file_path=None, whisper_model=None, selected_source_lang=None, vad_filter=None, diarize=None, **kwargs):
        return [{"start_seconds": 0, "end_seconds": 0, "Text": "hello"}]

    monkeypatch.setattr(audio_files, "speech_to_text", fake_speech_to_text)

    # Pretend the canonical Whisper model is not yet available locally
    def fake_check_status(model_name: str):
        return {
            "available": False,
            "message": f"Model {model_name} is not available locally",
            "model": model_name,
        }

    monkeypatch.setattr(audio_files, "check_transcription_model_status", fake_check_status)

    # Ensure the model name is parsed as a Whisper model with canonical id "large-v3"
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as atlib

    monkeypatch.setattr(atlib, "parse_transcription_model", lambda _: ("whisper", "large-v3", None), raising=True)

    result = audio_files.process_audio_files(
        inputs=[str(audio_path)],
        transcription_model="whisper-large-v3",
        transcription_language="en",
        perform_chunking=False,
        perform_analysis=False,
    )

    assert result["processed_count"] == 1
    item = result["results"][0]
    warnings = item.get("warnings") or []
    assert any("Model large-v3 is not available locally" in w for w in warnings)


@pytest.mark.unit
def test_default_title_from_audio_path_strips_hex_suffix():
    title = audio_files._default_title_from_audio_path("/tmp/My_Clip_ab12cd34.wav")
    assert title == "My_Clip"


@pytest.mark.unit
def test_default_title_from_audio_path_keeps_non_hex_suffix():
    title = audio_files._default_title_from_audio_path("/tmp/My_Clip_ab12cd3g.wav")
    assert title == "My_Clip_ab12cd3g"


@pytest.mark.unit
def test_process_audio_files_url_uses_sanitized_default_title(monkeypatch, tmp_path):
    downloaded_wav = tmp_path / "session_ab12cd34.wav"
    with wave.open(str(downloaded_wav), "wb") as wave_file:
        wave_file.setnchannels(1)
        wave_file.setsampwidth(2)
        wave_file.setframerate(8000)
        wave_file.writeframes(b"\x00\x00" * 8)

    monkeypatch.setattr(
        audio_files,
        "download_audio_file",
        lambda *args, **kwargs: str(downloaded_wav),
    )
    monkeypatch.setattr(
        audio_files,
        "check_transcription_model_status",
        lambda _model_name: {
            "available": True,
            "message": "ok",
            "model": "base",
        },
    )

    def fake_speech_to_text(**_kwargs):
        return [{"start_seconds": 0.0, "end_seconds": 1.0, "Text": "hello"}]

    monkeypatch.setattr(audio_files, "speech_to_text", fake_speech_to_text)

    result = audio_files.process_audio_files(
        inputs=["https://example.com/audio.mp3"],
        transcription_model="base",
        transcription_language="en",
        perform_chunking=False,
        perform_analysis=False,
        temp_dir=str(tmp_path),
    )

    assert result["processed_count"] == 1
    item = result["results"][0]
    assert item["status"] == "Success"
    assert item["metadata"]["title"] == "session"


@pytest.mark.unit
def test_process_audio_files_url_post_download_validation_rejected(monkeypatch, tmp_path):
    downloaded_payload = tmp_path / "session_payload.exe"
    downloaded_payload.write_bytes(b"MZ")

    monkeypatch.setattr(
        audio_files,
        "download_audio_file",
        lambda *args, **kwargs: str(downloaded_payload),
    )
    monkeypatch.setattr(
        audio_files,
        "check_transcription_model_status",
        lambda _model_name: {
            "available": True,
            "message": "ok",
            "model": "base",
        },
    )

    def _unexpected_stt(**_kwargs):
        raise AssertionError("speech_to_text should not run when URL validation fails")

    monkeypatch.setattr(audio_files, "speech_to_text", _unexpected_stt)

    result = audio_files.process_audio_files(
        inputs=["https://example.com/audio.mp3"],
        transcription_model="base",
        transcription_language="en",
        perform_chunking=False,
        perform_analysis=False,
        temp_dir=str(tmp_path),
    )

    assert result["processed_count"] == 0
    assert result["errors_count"] == 1
    assert result["results"][0]["status"] == "Error"
    assert "downloaded file failed validation" in str(
        result["results"][0].get("error", "")
    ).lower()
