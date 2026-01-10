import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files as audio_files


@pytest.mark.unit
def test_process_audio_files_rejects_local_path_outside_temp_dir(tmp_path):
     allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    outside_path = outside_dir / "sample.wav"

    result = audio_files.process_audio_files(
        inputs=[str(outside_path)],
        transcription_model="whisper-small",
        transcription_language="en",
        perform_chunking=False,
        perform_analysis=False,
        temp_dir=str(allowed_dir),
    )

    assert result["errors_count"] == 1
    item = result["results"][0]
    assert item["status"] == "Error"
    assert "rejected outside the temporary directory" in (item.get("error") or "")
