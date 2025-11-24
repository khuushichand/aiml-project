import json
import os
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
    ConversionError,
    perform_transcription,
    speech_to_text,
    convert_to_wav,
)
import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib as atlib


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

        # Simulate ffmpeg writing the output file during the conversion command
        if "-i" in cmd and cmd:
            output_target = Path(cmd[-1])
            output_target.write_bytes(b"RIFF")

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


@pytest.mark.unit
def test_convert_to_wav_respects_ffmpeg_path(monkeypatch, tmp_path):
    ffmpeg_path = tmp_path / "ffmpeg-bin"
    ffmpeg_path.write_text("#!/bin/sh\necho ffmpeg\n")

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

    monkeypatch.setenv("FFMPEG_PATH", str(ffmpeg_path))
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib.validate_audio_file",
        lambda path: (True, ""),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib.subprocess.run",
        fake_run,
    )

    output_path = convert_to_wav(str(input_file), overwrite=True)

    assert Path(output_path).name == "input.wav"
    # First call is version check, second is conversion
    assert commands[0][0] == str(ffmpeg_path)
    assert commands[1][0] == str(ffmpeg_path)


@pytest.mark.unit
def test_speech_to_text_persists_cache_files(monkeypatch, tmp_path):
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"\x00" * 2048)

    class _FakeSeg:
        def __init__(self, text="hello"):
            self.start = 0.0
            self.end = 1.0
            self.text = text

    class _FakeInfo:
        language = "en"
        language_probability = 0.9

    class _FakeModel:
        def transcribe(self, path, **kwargs):
            return [_FakeSeg()], _FakeInfo()

    # Ensure the stub model is returned regardless of check_download_status flag
    monkeypatch.setattr(atlib, "get_whisper_model", lambda *args, **kwargs: _FakeModel())
    monkeypatch.setattr(atlib, "processing_choice", "cpu")

    segments = speech_to_text(str(audio_file), whisper_model="tiny", selected_source_lang="en")
    assert segments

    out_file = audio_file.with_name(f"{audio_file.stem}-whisper_model-tiny.segments.json")
    pretty_file = audio_file.with_name(f"{audio_file.stem}-whisper_model-tiny.segments_pretty.json")

    assert out_file.exists()
    payload = json.loads(out_file.read_text())
    assert "segments" in payload and payload["segments"]
    assert pretty_file.exists()


@pytest.mark.unit
def test_perform_transcription_regenerates_on_invalid_cache(monkeypatch, tmp_path):
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"\x00" * 2048)

    model_name = "fake-model"
    base_path = audio_file.with_suffix("")
    cache_path = base_path.with_name(f"{base_path.name}-transcription_model-{model_name}.segments.json")
    cache_path.write_text("not valid json")

    regenerated = [{"Text": "regen"}]
    regen_called = {"called": False}

    monkeypatch.setattr(atlib, "convert_to_wav", lambda *args, **kwargs: str(audio_file))

    def fake_regenerate(path, model, vad_use, selected_source_lang="en"):
        regen_called["called"] = True
        return path, regenerated

    monkeypatch.setattr(atlib, "re_generate_transcription", fake_regenerate)

    audio_path, segments = perform_transcription(
        str(audio_file),
        offset=0,
        transcription_model=model_name,
        vad_use=False,
        overwrite=False,
        transcription_language="en",
    )

    assert regen_called["called"] is True
    assert audio_path == str(audio_file)
    assert segments == regenerated


@pytest.mark.unit
def test_prune_transcript_cache_limits_files(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import prune_transcript_cache

    cache_dir = tmp_path
    files = []
    for i in range(3):
        f = cache_dir / f"audio-whisper_model-tiny.segments{i}.json"
        f.write_text("data")
        # set older mtimes for earlier files
        os.utime(f, (f.stat().st_atime, f.stat().st_mtime - (i + 1) * 100))
        files.append(f)

    prune_transcript_cache(cache_dir, max_files_per_source=1)
    remaining = list(cache_dir.glob("audio-whisper_model-tiny.segments*.json"))
    assert len(remaining) == 1
    # newest file (i=0) should remain
    assert remaining[0].name == "audio-whisper_model-tiny.segments0.json"


@pytest.mark.unit
def test_prune_transcript_cache_age(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import prune_transcript_cache

    old_file = tmp_path / "audio-whisper_model-tiny.segments_old.json"
    new_file = tmp_path / "audio-whisper_model-tiny.segments_new.json"
    old_file.write_text("old")
    new_file.write_text("new")

    # Make old file older than 2 days
    two_days_seconds = 2 * 86400 + 10
    os.utime(old_file, (old_file.stat().st_atime - two_days_seconds, old_file.stat().st_mtime - two_days_seconds))

    prune_transcript_cache(tmp_path, max_age_days=1)
    assert not old_file.exists()
    assert new_file.exists()


@pytest.mark.unit
def test_speech_to_text_respects_persist_toggle(monkeypatch, tmp_path):
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"\x00" * 2048)

    class _Seg:
        start = 0.0
        end = 1.0
        text = "hello"

    class _Info:
        language = "en"
        language_probability = 0.9

    class _Model:
        def transcribe(self, *args, **kwargs):
            return [_Seg()], _Info()

    monkeypatch.setattr(atlib, "get_whisper_model", lambda *args, **kwargs: _Model())
    monkeypatch.setattr(atlib, "processing_choice", "cpu")

    segments = speech_to_text(str(audio_file), whisper_model="tiny", selected_source_lang="en", persist_segments=False)
    assert segments

    out_file = audio_file.with_name(f"{audio_file.stem}-whisper_model-tiny.segments.json")
    assert not out_file.exists()
