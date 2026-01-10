from pathlib import Path

import pytest

import tldw_Server_API.app.core.Workflows.adapters as wf_adapters


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_prompt_adapter_sanitizes_artifact_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def _capture_artifact(**kwargs):

             captured["uri"] = kwargs.get("uri")

    context = {"step_run_id": "../escape", "add_artifact": _capture_artifact}
    result = await wf_adapters.run_prompt_adapter({"template": "hello", "save_artifact": True}, context)
    assert result.get("text") == "hello"

    uri = captured.get("uri")
    assert isinstance(uri, str) and uri.startswith("file://")
    path = Path(uri[len("file://") :])
    base_dir = (tmp_path / "Databases" / "artifacts").resolve()
    assert path.resolve().is_relative_to(base_dir)
    assert path.exists()


@pytest.mark.asyncio
async def test_tts_adapter_sanitizes_output_filename(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    from tldw_Server_API.app.core.TTS import tts_service_v2 as tts_mod

    class _FakeTTSService:
        async def generate_speech(self, request, provider=None, fallback=True, voice_to_voice_start=None, voice_to_voice_route="audio.speech"):
            yield b"fake-audio"

    async def _fake_get_tts_service_v2(config=None):
        return _FakeTTSService()

    monkeypatch.setattr(tts_mod, "get_tts_service_v2", _fake_get_tts_service_v2, raising=True)

    config = {
        "input": "hello",
        "response_format": "mp3",
        "output_filename_template": "../evil",
    }
    context = {"step_run_id": "../escape"}
    result = await wf_adapters.run_tts_adapter(config, context)

    uri = result.get("audio_uri")
    assert isinstance(uri, str) and uri.startswith("file://")
    path = Path(uri[len("file://") :])
    base_dir = (tmp_path / "Databases" / "artifacts").resolve()
    assert path.resolve().is_relative_to(base_dir)
    assert path.name.endswith(".mp3")
    assert path.exists()


@pytest.mark.asyncio
async def test_stt_transcribe_rejects_outside_base(monkeypatch, tmp_path):
    user_base = tmp_path / "user_dbs"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(user_base))

    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"RIFF\x00\x00\x00WAVEfmt ")

    result = await wf_adapters.run_stt_transcribe_adapter(
        {"file_uri": f"file://{outside}"},
        {"user_id": 123},
    )
    assert result.get("error") == "file_access_denied"


@pytest.mark.asyncio
async def test_stt_transcribe_accepts_inside_base(monkeypatch, tmp_path):
    user_base = tmp_path / "user_dbs"
    user_id = 123
    user_dir = user_base / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(user_base))

    inside = user_dir / "valid.wav"
    inside.write_bytes(b"RIFF\x00\x00\x00WAVEfmt ")

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Transcription_Lib as stt_mod

    def _fake_speech_to_text(*_args, **_kwargs):

             return ([{"Text": "hello"}], "en")

    monkeypatch.setattr(stt_mod, "speech_to_text", _fake_speech_to_text, raising=True)

    result = await wf_adapters.run_stt_transcribe_adapter(
        {"file_uri": f"file://{inside}"},
        {"user_id": user_id},
    )
    assert result.get("text") == "hello"
    assert result.get("segments") == [{"Text": "hello"}]
    assert result.get("language") == "en"
