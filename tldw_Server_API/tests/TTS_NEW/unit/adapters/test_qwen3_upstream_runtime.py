import sys
import types

import numpy as np
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_tts_adapter import Qwen3TTSAdapter


class _FakeBackend:
    def generate_custom_voice(self, text, language=None, speaker=None, instruct=None, **_kwargs):
        return np.zeros(160, dtype=np.float32)


@pytest.fixture
def fake_qwen_module(monkeypatch):
    module = types.ModuleType("qwen_tts")

    class FakeQwen3TTS:
        @classmethod
        def from_pretrained(cls, model_id, **_kwargs):
            return _FakeBackend()

    module.Qwen3TTS = FakeQwen3TTS
    monkeypatch.setitem(sys.modules, "qwen_tts", module)
    return module


@pytest.mark.asyncio
async def test_upstream_runtime_handles_existing_custom_voice_flow(fake_qwen_module, monkeypatch):
    adapter = Qwen3TTSAdapter({"runtime": "upstream", "device": "cpu"})
    monkeypatch.setattr(adapter, "_resolve_torch_dtype", lambda: "float32")
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
    assert response.metadata["runtime"] == "upstream"
