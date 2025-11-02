import sys
import types
import asyncio
import numpy as np
import pytest

from tldw_Server_API.app.core.TTS.adapters.neutts_adapter import NeuTTSAdapter
from tldw_Server_API.app.core.TTS.adapters.base import TTSRequest, AudioFormat
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSGenerationError


class _FakeNeuTTSEngine:
    def __init__(self, *args, **kwargs):
        # Simulate HF transformers path (non-quantized)
        self._is_quantized_model = False

    def encode_reference(self, path):
        # Return some dummy codes
        return [1, 2, 3]

    def infer(self, text, ref_codes, ref_text):
        # Return a 0.5s of silence at 24kHz
        return np.zeros(12000, dtype=np.float32)


class _FakeNeuTTSEngineOnnx(_FakeNeuTTSEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Internal flag in upstream, irrelevant for adapter behavior here
        self._is_onnx_codec = True


class _FakeNeuTTSEngineError(_FakeNeuTTSEngine):
    def infer(self, text, ref_codes, ref_text):
        raise ValueError("No valid speech tokens found in the output.")


def _install_fake_engine(fake_cls):
    """Inject a fake NeuTTSAir into the vendored import path used by the adapter."""
    mod = types.ModuleType("tldw_Server_API.app.core.TTS.vendors.neuttsair.neutts")
    setattr(mod, "NeuTTSAir", fake_cls)
    sys.modules["tldw_Server_API.app.core.TTS.vendors.neuttsair.neutts"] = mod


@pytest.mark.asyncio
async def test_neutts_hf_path_generation(monkeypatch):
    _install_fake_engine(_FakeNeuTTSEngine)
    adapter = NeuTTSAdapter(config={
        "backbone_repo": "neuphonic/neutts-air",
        "codec_repo": "neuphonic/neucodec",
        "sample_rate": 24000,
    })
    assert await adapter.ensure_initialized()
    # Use ref_codes path to avoid validator requiring a real audio container
    req = TTSRequest(
        text="hello",
        format=AudioFormat.PCM,
        stream=False,
        extra_params={"reference_text": "hello world", "ref_codes": [1, 2, 3]},
    )
    resp = await adapter.generate(req)
    assert resp.audio_data and len(resp.audio_data) > 0
    assert resp.format == AudioFormat.PCM


@pytest.mark.asyncio
async def test_neutts_onnx_codec_generation(monkeypatch):
    _install_fake_engine(_FakeNeuTTSEngineOnnx)
    adapter = NeuTTSAdapter(config={
        "backbone_repo": "neuphonic/neutts-air",
        "codec_repo": "neuphonic/neucodec-onnx-decoder",
        "sample_rate": 24000,
    })
    assert await adapter.ensure_initialized()
    req = TTSRequest(
        text="check",
        format=AudioFormat.PCM,
        stream=False,
        extra_params={"reference_text": "ref", "ref_codes": [3, 2, 1]},
    )
    resp = await adapter.generate(req)
    assert resp.audio_data and len(resp.audio_data) > 0


@pytest.mark.asyncio
async def test_neutts_no_speech_tokens_error(monkeypatch):
    _install_fake_engine(_FakeNeuTTSEngineError)
    adapter = NeuTTSAdapter(config={
        "backbone_repo": "neuphonic/neutts-air",
        "codec_repo": "neuphonic/neucodec",
        "sample_rate": 24000,
    })
    assert await adapter.ensure_initialized()
    req = TTSRequest(
        text="fail",
        format=AudioFormat.PCM,
        stream=False,
        extra_params={"reference_text": "text", "ref_codes": [1, 2]},
    )
    with pytest.raises(TTSGenerationError):
        await adapter.generate(req)
