import sys
import types

import numpy as np
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.luxtts_adapter import LuxTTSAdapter


class _FakeLuxTTS:
    def __init__(self, model_path=None, device="cpu", threads=2, holder=None):
        self.model_path = model_path
        self.device = device
        self.threads = threads
        self.calls = []
        self.vocos = types.SimpleNamespace(return_48k=True)
        if isinstance(holder, dict):
            holder["instance"] = self

    def encode_prompt(self, prompt_audio, duration=5, rms=0.001):
        self.calls.append(("encode", prompt_audio, duration, rms))
        return {
            "prompt_tokens": [1],
            "prompt_features_lens": [1],
            "prompt_features": [1],
            "prompt_rms": [0.1],
        }

    def generate_speech(
        self,
        text,
        encode_dict,
        num_steps=4,
        guidance_scale=3.0,
        t_shift=0.5,
        speed=1.0,
        return_smooth=False,
    ):
        self.calls.append(
            ("generate", text, num_steps, guidance_scale, t_shift, speed, return_smooth)
        )
        return np.ones((1, 3200), dtype=np.float32) * 0.1


def _inject_luxtts(monkeypatch, holder):
    module = types.ModuleType("zipvoice.luxvoice")

    class _LuxTTSFactory(_FakeLuxTTS):
        def __init__(self, model_path=None, device="cpu", threads=2):
            super().__init__(model_path=model_path, device=device, threads=threads, holder=holder)

    module.LuxTTS = _LuxTTSFactory
    pkg = types.ModuleType("zipvoice")
    monkeypatch.setitem(sys.modules, "zipvoice", pkg)
    monkeypatch.setitem(sys.modules, "zipvoice.luxvoice", module)

_VOICE_REF = b"RIFF" + b"\x00" * 12


@pytest.mark.asyncio
async def test_luxtts_generate_non_stream(monkeypatch):
    holder = {}
    _inject_luxtts(monkeypatch, holder)

    adapter = LuxTTSAdapter(
        {
            "device": "cpu",
            "lux_tts_threads": 1,
            "sample_rate": 48000,
            "validate_reference": False,
            "convert_reference": False,
        }
    )

    request = TTSRequest(
        text="Hello LuxTTS",
        format=AudioFormat.MP3,
        voice_reference=_VOICE_REF,
        stream=False,
        extra_params={"prompt_duration": 4.0, "prompt_rms": 0.002, "num_steps": 3},
    )

    response = await adapter.generate(request)
    assert response.audio_data and isinstance(response.audio_data, (bytes, bytearray))
    assert response.audio_stream is None
    assert response.provider == "lux_tts"
    assert response.sample_rate == 48000

    instance = holder.get("instance")
    assert instance is not None
    assert instance.device == "cpu"
    assert instance.calls and instance.calls[0][0] == "encode"
    assert instance.calls[1][0] == "generate"

    await adapter.close()


@pytest.mark.asyncio
async def test_luxtts_streaming_chunks(monkeypatch):
    holder = {}
    _inject_luxtts(monkeypatch, holder)

    adapter = LuxTTSAdapter(
        {
            "device": "cpu",
            "validate_reference": False,
            "convert_reference": False,
            "stream_chunk_samples": 512,
        }
    )

    request = TTSRequest(
        text="Stream LuxTTS",
        format=AudioFormat.PCM,
        voice_reference=_VOICE_REF,
        stream=True,
        extra_params={"stream_chunk_samples": 256},
    )

    response = await adapter.generate(request)
    assert response.audio_stream is not None
    chunks = [chunk async for chunk in response.audio_stream]
    assert len(chunks) >= 2
    assert all(isinstance(c, (bytes, bytearray)) for c in chunks)

    await adapter.close()
