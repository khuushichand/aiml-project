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


@pytest.mark.asyncio
async def test_stt_transcribe_unsafe_access_requires_allowlist(monkeypatch, tmp_path):
    user_base = tmp_path / "user_dbs"
    user_id = 123
    user_dir = user_base / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(user_base))
    monkeypatch.setenv("WORKFLOWS_ALLOW_UNSAFE_FILE_ACCESS", "true")
    monkeypatch.setenv("WORKFLOWS_FILE_ALLOWLIST", str(user_dir))

    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"RIFF\x00\x00\x00WAVEfmt ")

    result = await wf_adapters.run_stt_transcribe_adapter(
        {"file_uri": f"file://{outside}"},
        {"user_id": user_id},
    )
    assert result.get("error") == "file_access_denied"


@pytest.mark.asyncio
async def test_stt_transcribe_unsafe_access_allows_allowlist(monkeypatch, tmp_path):
    user_base = tmp_path / "user_dbs"
    user_id = 123
    user_dir = user_base / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(user_base))
    monkeypatch.setenv("WORKFLOWS_ALLOW_UNSAFE_FILE_ACCESS", "true")
    monkeypatch.setenv("WORKFLOWS_FILE_ALLOWLIST", str(tmp_path))

    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"RIFF\x00\x00\x00WAVEfmt ")

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Transcription_Lib as stt_mod

    def _fake_speech_to_text(*_args, **_kwargs):
        return ([{"Text": "hello"}], "en")

    monkeypatch.setattr(stt_mod, "speech_to_text", _fake_speech_to_text, raising=True)

    result = await wf_adapters.run_stt_transcribe_adapter(
        {"file_uri": f"file://{outside}"},
        {"user_id": user_id},
    )
    assert result.get("text") == "hello"
    assert result.get("segments") == [{"Text": "hello"}]
    assert result.get("language") == "en"


@pytest.mark.asyncio
async def test_stt_transcribe_unsafe_access_tenant_allowlist_override(monkeypatch, tmp_path):
    user_base = tmp_path / "user_dbs"
    user_id = 123
    user_dir = user_base / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(user_base))
    monkeypatch.setenv("WORKFLOWS_ALLOW_UNSAFE_FILE_ACCESS", "true")
    monkeypatch.setenv("WORKFLOWS_FILE_ALLOWLIST", str(tmp_path))
    monkeypatch.setenv("WORKFLOWS_FILE_ALLOWLIST_ACME", str(user_dir))

    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"RIFF\x00\x00\x00WAVEfmt ")

    result = await wf_adapters.run_stt_transcribe_adapter(
        {"file_uri": f"file://{outside}"},
        {"user_id": user_id, "tenant_id": "acme"},
    )
    assert result.get("error") == "file_access_denied"


def test_resolve_workflow_file_path_allows_relative_under_base(monkeypatch, tmp_path):
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    monkeypatch.setenv("WORKFLOWS_FILE_BASE_DIR", str(base_dir))

    resolved = wf_adapters._resolve_workflow_file_path("subdir/file.txt", {})
    assert resolved == (base_dir / "subdir" / "file.txt").resolve(strict=False)
    assert resolved.resolve(strict=False).is_relative_to(base_dir.resolve(strict=False))


def test_resolve_workflow_file_path_allows_absolute_under_base(monkeypatch, tmp_path):
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    monkeypatch.setenv("WORKFLOWS_FILE_BASE_DIR", str(base_dir))

    inside = base_dir / "inside.txt"
    resolved = wf_adapters._resolve_workflow_file_path(str(inside), {})
    assert resolved == inside.resolve(strict=False)
    assert resolved.resolve(strict=False).is_relative_to(base_dir.resolve(strict=False))


def test_resolve_workflow_file_path_rejects_traversal(monkeypatch, tmp_path):
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    monkeypatch.setenv("WORKFLOWS_FILE_BASE_DIR", str(base_dir))

    with pytest.raises(wf_adapters.AdapterError):
        wf_adapters._resolve_workflow_file_path("../escape.txt", {})


def test_resolve_workflow_file_path_rejects_absolute_outside_base(monkeypatch, tmp_path):
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    monkeypatch.setenv("WORKFLOWS_FILE_BASE_DIR", str(base_dir))

    outside = tmp_path / "outside.txt"
    with pytest.raises(wf_adapters.AdapterError):
        wf_adapters._resolve_workflow_file_path(str(outside), {})


def test_resolve_workflow_file_path_unsafe_allows_allowlist(monkeypatch, tmp_path):
    base_dir = tmp_path / "base"
    allow_dir = tmp_path / "allow"
    base_dir.mkdir()
    allow_dir.mkdir()
    monkeypatch.setenv("WORKFLOWS_FILE_BASE_DIR", str(base_dir))
    monkeypatch.setenv("WORKFLOWS_ALLOW_UNSAFE_FILE_ACCESS", "true")
    monkeypatch.setenv("WORKFLOWS_FILE_ALLOWLIST", str(allow_dir))

    target = allow_dir / "allowed.txt"
    resolved = wf_adapters._resolve_workflow_file_path(str(target), {})
    assert resolved == target.resolve(strict=False)
    assert resolved.resolve(strict=False).is_relative_to(allow_dir.resolve(strict=False))


def test_resolve_workflow_file_path_unsafe_denies_without_allowlist(monkeypatch, tmp_path):
    base_dir = tmp_path / "base"
    allow_dir = tmp_path / "allow"
    base_dir.mkdir()
    allow_dir.mkdir()
    monkeypatch.setenv("WORKFLOWS_FILE_BASE_DIR", str(base_dir))
    monkeypatch.setenv("WORKFLOWS_ALLOW_UNSAFE_FILE_ACCESS", "true")
    monkeypatch.setenv("WORKFLOWS_FILE_ALLOWLIST", str(base_dir))

    target = allow_dir / "blocked.txt"
    with pytest.raises(wf_adapters.AdapterError):
        wf_adapters._resolve_workflow_file_path(str(target), {})
