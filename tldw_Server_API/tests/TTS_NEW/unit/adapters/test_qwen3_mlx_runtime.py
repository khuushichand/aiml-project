import asyncio
import platform
import sys
import types

import numpy as np
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_tts_adapter import Qwen3TTSAdapter
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSValidationError


@pytest.mark.asyncio
async def test_mlx_runtime_reports_preset_custom_voice_only(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    adapter = Qwen3TTSAdapter({"runtime": "mlx", "device": "mps"})

    await adapter.ensure_initialized()
    caps = await adapter.get_capabilities()

    assert caps.metadata["runtime"] == "mlx"
    assert caps.metadata["supported_modes"] == ["custom_voice_preset"]
    assert caps.metadata["supports_uploaded_custom_voices"] is False
    assert caps.supports_voice_cloning is False
    assert caps.supports_streaming is True


@pytest.fixture
def fake_mlx_audio_module(monkeypatch):
    mlx_audio_module = types.ModuleType("mlx_audio")
    mlx_audio_tts_module = types.ModuleType("mlx_audio.tts")
    mlx_audio_utils_module = types.ModuleType("mlx_audio.tts.utils")
    load_calls = {"count": 0}

    class _FakeResult:
        def __init__(self):
            self.audio = np.zeros(160, dtype=np.float32)
            self.sample_rate = 24000

    class _FakeModel:
        def generate(self, **_kwargs):
            yield _FakeResult()

    def fake_load_model(_model_id):
        load_calls["count"] += 1
        return _FakeModel()

    mlx_audio_utils_module.load_model = fake_load_model

    monkeypatch.setitem(sys.modules, "mlx_audio", mlx_audio_module)
    monkeypatch.setitem(sys.modules, "mlx_audio.tts", mlx_audio_tts_module)
    monkeypatch.setitem(sys.modules, "mlx_audio.tts.utils", mlx_audio_utils_module)
    return load_calls


@pytest.mark.asyncio
async def test_mlx_runtime_generates_preset_speaker_audio(fake_mlx_audio_module, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    adapter = Qwen3TTSAdapter({"runtime": "mlx", "device": "mps"})

    await adapter.ensure_initialized()

    request = TTSRequest(
        text="hello",
        voice="Vivian",
        format=AudioFormat.PCM,
        stream=False,
    )
    request.model = "auto"

    response = await adapter.generate(request)

    assert response.audio_content
    assert response.metadata["runtime"] == "mlx"


@pytest.mark.asyncio
async def test_mlx_runtime_offloads_model_load_and_generation(fake_mlx_audio_module, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    to_thread_calls = []

    async def fake_to_thread(func, *args, **kwargs):
        to_thread_calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    adapter = Qwen3TTSAdapter({"runtime": "mlx", "device": "mps"})

    await adapter.ensure_initialized()

    request = TTSRequest(
        text="hello",
        voice="Vivian",
        format=AudioFormat.PCM,
        stream=False,
    )
    request.model = "auto"

    await adapter.generate(request)

    assert to_thread_calls == ["fake_load_model", "_run_generation"]


@pytest.mark.asyncio
async def test_mlx_runtime_serializes_concurrent_model_loads(fake_mlx_audio_module, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    async def fake_to_thread(func, *args, **kwargs):
        await asyncio.sleep(0)
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    adapter = Qwen3TTSAdapter({"runtime": "mlx", "device": "mps"})

    await adapter.ensure_initialized()
    runtime = adapter._get_runtime()

    models = await asyncio.gather(runtime._get_model("auto"), runtime._get_model("auto"))

    assert models[0][0] is models[1][0]
    assert fake_mlx_audio_module["count"] == 1


@pytest.mark.asyncio
async def test_mlx_runtime_rejects_unknown_non_custom_voice(fake_mlx_audio_module, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    adapter = Qwen3TTSAdapter({"runtime": "mlx", "device": "mps"})

    await adapter.ensure_initialized()

    request = TTSRequest(
        text="hello",
        voice="not-a-real-speaker",
        format=AudioFormat.PCM,
        stream=False,
    )
    request.model = "auto"

    with pytest.raises(TTSValidationError):
        await adapter.generate(request)


@pytest.mark.asyncio
async def test_mlx_runtime_stream_request_uses_buffered_fallback(fake_mlx_audio_module, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    adapter = Qwen3TTSAdapter({"runtime": "mlx", "device": "mps"})

    await adapter.ensure_initialized()

    request = TTSRequest(
        text="hello",
        voice="Vivian",
        format=AudioFormat.PCM,
        stream=True,
    )
    request.model = "auto"

    response = await adapter.generate(request)
    chunks = [chunk async for chunk in response.audio_stream]

    assert chunks
    assert response.metadata["runtime"] == "mlx"
    assert response.metadata["streaming_fallback"] == "buffered"
