import pytest


pytestmark = pytest.mark.unit


def test_convert_to_wav_cancelled_before_ffmpeg(tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
        TranscriptionCancelled,
        convert_to_wav,
    )

    sample_path = tmp_path / "sample.mp3"
    sample_path.write_bytes(b"0" * 2048)

    with pytest.raises(TranscriptionCancelled):
        convert_to_wav(
            str(sample_path),
            base_dir=tmp_path,
            cancel_check=lambda: True,
        )


def test_process_audio_files_marks_remaining_on_cancel(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
        TranscriptionCancelled,
    )

    first = tmp_path / "first.mp3"
    second = tmp_path / "second.mp3"
    first.write_bytes(b"1")
    second.write_bytes(b"1")

    def _raise_cancel(*_args, **_kwargs):
        raise TranscriptionCancelled("Cancelled by user")

    monkeypatch.setattr(Audio_Files, "convert_to_wav", _raise_cancel)

    results = Audio_Files.process_audio_files(
        inputs=[str(first), str(second)],
        transcription_model="base",
        temp_dir=str(tmp_path),
        perform_chunking=False,
        perform_analysis=False,
        cancel_check=lambda: False,
    )

    statuses = [item.get("status") for item in results.get("results", [])]
    assert statuses == ["Cancelled", "Cancelled"]
