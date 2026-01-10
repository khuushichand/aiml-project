import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Files as audio_files


@pytest.mark.unit
def test_format_transcription_with_timestamps_uses_start_seconds():
     segments = [{"start_seconds": 1.5, "end_seconds": 2.5, "Text": "Hello"}]
    result = audio_files.format_transcription_with_timestamps(
        segments,
        keep_timestamps=True,
    )
    lines = result.splitlines()
    assert len(lines) == 1
    assert "Hello" in lines[0]
    assert "00:00:01" in lines[0]
    assert "00:00:02" in lines[0]


@pytest.mark.unit
def test_format_transcription_with_timestamps_uses_time_strings():
     segments = [{"Time_Start": "00:00:05", "Time_End": "00:00:07", "Text": "Hi"}]
    result = audio_files.format_transcription_with_timestamps(
        segments,
        keep_timestamps=True,
    )
    lines = result.splitlines()
    assert len(lines) == 1
    assert "[00:00:05-00:00:07] Hi" == lines[0]


@pytest.mark.unit
def test_format_transcription_with_timestamps_plain_text():
     segments = [
        {"Time_Start": 0, "Time_End": 1, "Text": "Hi"},
        {"Time_Start": 1, "Time_End": 2, "Text": "  "},
    ]
    result = audio_files.format_transcription_with_timestamps(
        segments,
        keep_timestamps=False,
    )
    assert result == "Hi"
