from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
    ConversionError,
    convert_to_wav,
)


@pytest.mark.unit
def test_convert_to_wav_includes_duration(monkeypatch, tmp_path):
    input_file = tmp_path / "input.mp3"
    input_file.write_bytes(b"\x00" * 2048)

    commands = []

    def fake_run(cmd, *args, **kwargs):
        commands.append(cmd)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib.validate_audio_file",
        lambda path: (True, ""),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib.subprocess.run",
        fake_run,
    )

    output_path = convert_to_wav(str(input_file), offset=5, end_time=9, overwrite=True)

    assert Path(output_path).suffix == ".wav"
    assert len(commands) >= 2  # first is version check
    conversion_cmd = commands[1]
    assert "-t" in conversion_cmd
    # duration should be end_time - offset => 4 seconds
    assert "4" in conversion_cmd


@pytest.mark.unit
def test_convert_to_wav_rejects_invalid_range(tmp_path):
    invalid_clip = tmp_path / "clip.mp4"
    invalid_clip.write_bytes(b"\x00" * 2048)
    with pytest.raises(ConversionError):
        convert_to_wav(str(invalid_clip), offset=10, end_time=9)
