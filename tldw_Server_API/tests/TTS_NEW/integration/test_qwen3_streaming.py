import sys
import types

import numpy as np
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_tts_adapter import Qwen3TTSAdapter


@pytest.fixture
def fake_qwen_stream_module(monkeypatch):
    module = types.ModuleType("qwen_tts")

    class StreamBackend:
        async def stream_custom_voice(self, text, language=None, speaker=None, **_kwargs):
            yield np.zeros(160, dtype=np.int16)
            yield np.ones(160, dtype=np.int16)

    class FakeQwen3TTS:
        @classmethod
        def from_pretrained(cls, model_id, **_kwargs):
            return StreamBackend()

    module.Qwen3TTS = FakeQwen3TTS
    monkeypatch.setitem(sys.modules, "qwen_tts", module)


@pytest.mark.asyncio
async def test_qwen3_streaming_returns_chunks(fake_qwen_stream_module):
    adapter = Qwen3TTSAdapter({"device": "cpu", "model": "auto"})
    await adapter.ensure_initialized()

    request = TTSRequest(
        text="Hello",
        voice="Vivian",
        language="en",
        format=AudioFormat.PCM,
        stream=True,
    )
    request.model = "auto"

    response = await adapter.generate(request)
    assert response.audio_stream is not None

    chunks = []
    async for chunk in response.audio_stream:
        chunks.append(chunk)

    assert chunks
    assert any(chunk for chunk in chunks)
