import sys
import types
import platform

import numpy as np
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_tts_adapter import Qwen3TTSAdapter


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


@pytest.fixture
def fake_mlx_audio_module(monkeypatch):
    mlx_audio_module = types.ModuleType("mlx_audio")
    mlx_audio_tts_module = types.ModuleType("mlx_audio.tts")
    mlx_audio_utils_module = types.ModuleType("mlx_audio.tts.utils")

    class _FakeResult:
        def __init__(self):
            self.audio = np.zeros(160, dtype=np.float32)
            self.sample_rate = 24000

    class _FakeModel:
        def generate(self, **_kwargs):
            yield _FakeResult()

    mlx_audio_utils_module.load_model = lambda _model_id: _FakeModel()

    monkeypatch.setitem(sys.modules, "mlx_audio", mlx_audio_module)
    monkeypatch.setitem(sys.modules, "mlx_audio.tts", mlx_audio_tts_module)
    monkeypatch.setitem(sys.modules, "mlx_audio.tts.utils", mlx_audio_utils_module)


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
