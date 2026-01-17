import sys
import types

import numpy as np
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.supertonic2_adapter import Supertonic2OnnxAdapter
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSModelNotFoundError


class _DummyEngine:
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self.calls = []

    def __call__(self, text: str, lang: str, style, total_step: int, speed: float):
        self.calls.append((text, lang, style, total_step, speed))
        wav = np.ones((1, int(self.sample_rate * 0.25)), dtype=np.float32)
        duration = np.array([0.25])
        return wav, duration


def _inject_vendor(monkeypatch, engine: _DummyEngine, call_log: dict):
    module = types.SimpleNamespace()

    def load_text_to_speech(onnx_dir: str, use_gpu: bool = False):
        call_log["onnx_dir"] = onnx_dir
        call_log["use_gpu"] = use_gpu
        return engine

    def load_voice_style(paths, verbose: bool = False):
        call_log["voice_paths"] = list(paths)
        return {"style": "dummy"}

    module.load_text_to_speech = load_text_to_speech
    module.load_voice_style = load_voice_style
    monkeypatch.setitem(sys.modules, "tldw_Server_API.app.core.TTS.vendors.supertonic2", module)


@pytest.mark.asyncio
async def test_supertonic2_initialize_and_generate(monkeypatch, tmp_path):
    onnx_dir = tmp_path / "onnx"
    onnx_dir.mkdir()
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    default_voice = voices_dir / "M1.json"
    default_voice.write_text("{}")
    alt_voice = voices_dir / "F1.json"
    alt_voice.write_text("{}")

    engine = _DummyEngine(sample_rate=24000)
    call_log = {}
    _inject_vendor(monkeypatch, engine, call_log)

    adapter = Supertonic2OnnxAdapter(
        {
            "model_path": str(onnx_dir),
            "sample_rate": 24000,
            "device": "cpu",
            "extra_params": {
                "voice_styles_dir": str(voices_dir),
                "default_voice": "supertonic2_m1",
                "voice_files": {
                    "supertonic2_m1": "M1.json",
                    "supertonic2_f1": "F1.json",
                },
                "stream_chunk_size": 16,
                "default_total_step": 7,
            },
        }
    )

    request = TTSRequest(
        text="hello world",
        voice="supertonic2_m1",
        format=AudioFormat.MP3,
        speed=1.1,
        language="ko",
        stream=False,
    )

    response = await adapter.generate(request)
    assert response.audio_data and isinstance(response.audio_data, (bytes, bytearray))
    assert response.audio_stream is None
    assert response.voice_used == "supertonic2_m1"
    assert engine.calls and engine.calls[0][0] == "hello world"
    assert engine.calls[0][1] == "ko"
    assert engine.calls[0][3] == 7
    assert pytest.approx(engine.calls[0][4], rel=1e-3) == 1.1
    assert call_log["onnx_dir"] == str(onnx_dir)
    assert call_log["use_gpu"] is False
    assert call_log["voice_paths"] == [str(default_voice)]

    await adapter.close()


@pytest.mark.asyncio
async def test_supertonic2_streaming_chunks(monkeypatch, tmp_path):
    onnx_dir = tmp_path / "onnx"
    onnx_dir.mkdir()
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    default_voice = voices_dir / "M1.json"
    default_voice.write_text("{}")

    engine = _DummyEngine(sample_rate=24000)
    call_log = {}
    _inject_vendor(monkeypatch, engine, call_log)

    adapter = Supertonic2OnnxAdapter(
        {
            "model_path": str(onnx_dir),
            "sample_rate": 24000,
            "extra_params": {
                "voice_styles_dir": str(voices_dir),
                "default_voice": "supertonic2_m1",
                "voice_files": {
                    "supertonic2_m1": "M1.json",
                },
                "stream_chunk_size": 8,
            },
        }
    )

    request = TTSRequest(
        text="stream me",
        voice="supertonic2_m1",
        format=AudioFormat.WAV,
        speed=1.0,
        language="en",
        stream=True,
    )

    response = await adapter.generate(request)
    assert response.audio_stream is not None
    chunks = [chunk async for chunk in response.audio_stream]
    assert len(chunks) >= 2
    assert all(isinstance(c, (bytes, bytearray)) for c in chunks)

    await adapter.close()


@pytest.mark.asyncio
async def test_supertonic2_missing_default_voice(monkeypatch, tmp_path):
    onnx_dir = tmp_path / "onnx"
    onnx_dir.mkdir()
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()

    engine = _DummyEngine(sample_rate=24000)
    call_log = {}
    _inject_vendor(monkeypatch, engine, call_log)

    adapter = Supertonic2OnnxAdapter(
        {
            "model_path": str(onnx_dir),
            "sample_rate": 24000,
            "extra_params": {
                "voice_styles_dir": str(voices_dir),
                "default_voice": "supertonic2_m1",
                "voice_files": {
                    "supertonic2_m1": "missing.json",
                },
            },
        }
    )

    with pytest.raises(TTSModelNotFoundError):
        await adapter.ensure_initialized()
