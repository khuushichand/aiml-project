from types import SimpleNamespace
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Transcription_Lib as audio_lib


@pytest.mark.unit
def test_validate_audio_file_prefers_ffprobe_sibling(monkeypatch, tmp_path):
    """Ensure ffprobe executable sitting alongside ffmpeg is detected and used."""
    fake_ffmpeg = tmp_path / "ffmpeg.exe"
    fake_ffmpeg.write_bytes(b"")
    fake_ffprobe = tmp_path / "ffprobe.exe"
    fake_ffprobe.write_bytes(b"")

    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"\x00" * 2048)

    monkeypatch.setattr(audio_lib, "_find_ffmpeg", lambda: str(fake_ffmpeg))
    monkeypatch.setattr(audio_lib.shutil, "which", lambda command: None if command == "ffprobe" else str(fake_ffmpeg))

    run_result = SimpleNamespace(returncode=0, stdout='{"streams": [{"channels": 2}]}', stderr="")

    called = {}

    def _fake_run(cmd, *args, **kwargs):
        called["cmd"] = cmd
        return run_result

    monkeypatch.setattr(audio_lib.subprocess, "run", _fake_run)

    is_valid, message = audio_lib.validate_audio_file(str(audio_path))

    assert is_valid
    assert message == ""

    assert Path(called["cmd"][0]) == fake_ffprobe
