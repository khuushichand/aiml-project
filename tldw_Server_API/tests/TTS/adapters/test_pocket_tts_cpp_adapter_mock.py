# test_pocket_tts_cpp_adapter_mock.py
# Description: Mock/unit tests for PocketTTS.cpp CLI adapter
#
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, ProviderStatus, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_adapter import PocketTTSCppAdapter
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSInvalidVoiceReferenceError,
    TTSModelNotFoundError,
)


pytestmark = pytest.mark.unit


def _make_wav_bytes(*, sample_rate: int = 24000, channels: int = 1) -> bytes:
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * 32)
    return buffer.getvalue()


def _write_cpp_assets(root: Path) -> tuple[Path, Path, Path]:
    binary_path = root / "bin" / "pocket-tts"
    model_path = root / "models" / "pocket_tts_cpp" / "onnx"
    tokenizer_path = root / "models" / "pocket_tts_cpp" / "tokenizer.model"

    binary_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.mkdir(parents=True, exist_ok=True)
    tokenizer_path.parent.mkdir(parents=True, exist_ok=True)

    binary_path.write_text("#!/bin/sh\n", encoding="utf-8")
    binary_path.chmod(0o755)
    tokenizer_path.write_bytes(b"tokenizer")
    for name in [
        "flow_lm_main_int8.onnx",
        "flow_lm_flow_int8.onnx",
        "mimi_decoder_int8.onnx",
        "mimi_encoder.onnx",
        "text_conditioner.onnx",
    ]:
        (model_path / name).write_bytes(b"")

    return binary_path, model_path, tokenizer_path


def _build_adapter(root: Path, *, prefer_stdout: bool = True) -> PocketTTSCppAdapter:
    binary_path, model_path, tokenizer_path = _write_cpp_assets(root)
    return PocketTTSCppAdapter(
        {
            "binary_path": str(binary_path),
            "model_path": str(model_path),
            "tokenizer_path": str(tokenizer_path),
            "timeout": 30,
            "prefer_stdout": prefer_stdout,
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing_path",
    ["binary", "tokenizer", "onnx"],
)
async def test_initialize_requires_binary_tokenizer_and_onnx_assets(tmp_path, missing_path):
    adapter = _build_adapter(tmp_path)

    if missing_path == "binary":
        Path(adapter.binary_path).unlink()
    elif missing_path == "tokenizer":
        Path(adapter.tokenizer_path).unlink()
    else:
        (Path(adapter.model_path) / "mimi_decoder_int8.onnx").unlink()

    with pytest.raises(TTSModelNotFoundError):
        await adapter.initialize()


@pytest.mark.asyncio
async def test_non_streaming_generation_uses_provider_voice_path_and_stdout_for_pcm(tmp_path, monkeypatch):
    adapter = _build_adapter(tmp_path, prefer_stdout=True)
    adapter._initialized = True
    adapter._status = ProviderStatus.AVAILABLE

    voice_path = tmp_path / "voices" / "providers" / "pocket_tts_cpp" / "custom_voice-1.wav"
    voice_path.parent.mkdir(parents=True, exist_ok=True)
    voice_path.write_bytes(_make_wav_bytes())

    stdout_pcm = np.array([0.0, 0.5, -0.5], dtype=np.float32).tobytes()
    captured: dict[str, tuple[str, ...]] = {}

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return stdout_pcm, b""

    async def _fake_create_subprocess_exec(*cmd, **kwargs):
        captured["cmd"] = tuple(str(part) for part in cmd)
        return _FakeProcess()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_adapter.asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec,
        raising=True,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_adapter.tempfile.NamedTemporaryFile",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("stdout transport should not create a temp output file")),
        raising=True,
    )

    request = TTSRequest(
        text="hello world",
        voice="custom:voice-1",
        format=AudioFormat.PCM,
        stream=False,
        extra_params={"pocket_tts_cpp_voice_path": str(voice_path)},
    )

    response = await adapter.generate(request)

    assert response.audio_data is not None
    assert response.audio_data != stdout_pcm
    assert response.metadata["transport"] == "stdout"
    assert "--stdout" in captured["cmd"]
    assert str(voice_path) in captured["cmd"]


@pytest.mark.asyncio
async def test_non_streaming_generation_requires_provider_managed_voice_path(tmp_path):
    adapter = _build_adapter(tmp_path)
    adapter._initialized = True
    adapter._status = ProviderStatus.AVAILABLE

    request = TTSRequest(
        text="hello world",
        voice="custom:voice-1",
        format=AudioFormat.WAV,
        stream=False,
        voice_reference=_make_wav_bytes(),
        extra_params={},
    )

    with pytest.raises(TTSInvalidVoiceReferenceError):
        await adapter.generate(request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target_format",
    [AudioFormat.WAV, AudioFormat.MP3, AudioFormat.OPUS, AudioFormat.FLAC, AudioFormat.PCM, AudioFormat.AAC],
)
async def test_non_streaming_generation_normalizes_file_output_to_requested_format(tmp_path, monkeypatch, target_format):
    adapter = _build_adapter(tmp_path, prefer_stdout=False)
    adapter._initialized = True
    adapter._status = ProviderStatus.AVAILABLE

    voice_path = tmp_path / "voices" / "providers" / "pocket_tts_cpp" / "custom_voice-2.wav"
    voice_path.parent.mkdir(parents=True, exist_ok=True)
    voice_path.write_bytes(_make_wav_bytes())

    recorded: dict[str, object] = {}
    target_bytes = b"normalized-" + target_format.value.encode("utf-8")
    wav_bytes = _make_wav_bytes()

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            output_path = Path(str(recorded["output_path"]))
            output_path.write_bytes(wav_bytes)
            return b"", b""

    async def _fake_create_subprocess_exec(*cmd, **kwargs):
        recorded["cmd"] = tuple(str(part) for part in cmd)
        recorded["output_path"] = cmd[-1]
        return _FakeProcess()

    async def _fake_convert_format(input_path: Path, output_path: Path, target_format_arg: str, **kwargs):
        recorded["convert"] = (Path(input_path), Path(output_path), target_format_arg, kwargs)
        Path(output_path).write_bytes(target_bytes)
        return True

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_adapter.asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec,
        raising=True,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.adapters.pocket_tts_cpp_adapter.AudioConverter.convert_format",
        _fake_convert_format,
        raising=True,
    )

    request = TTSRequest(
        text="hello world",
        voice="custom:voice-2",
        format=target_format,
        stream=False,
        extra_params={"pocket_tts_cpp_voice_path": str(voice_path)},
    )

    response = await adapter.generate(request)

    if target_format == AudioFormat.WAV:
        expected_bytes = wav_bytes
    elif target_format == AudioFormat.PCM:
        import io
        import wave

        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            expected_bytes = wav_file.readframes(wav_file.getnframes())
    else:
        expected_bytes = target_bytes
    assert response.audio_data == expected_bytes
    assert response.metadata["transport"] == "file"
    assert "--stdout" not in recorded["cmd"]
    assert str(voice_path) in recorded["cmd"]
    if target_format in {AudioFormat.WAV, AudioFormat.PCM}:
        assert "convert" not in recorded
    else:
        assert recorded["convert"][2] == target_format.value
