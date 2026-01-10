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
