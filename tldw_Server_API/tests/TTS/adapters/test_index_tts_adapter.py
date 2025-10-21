import base64
import io
import wave
from pathlib import Path

import numpy as np
import pytest
from unittest.mock import MagicMock

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, ProviderStatus, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.index_tts_adapter import IndexTTS2Adapter
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSUnsupportedFormatError,
    TTSValidationError,
)
from tldw_Server_API.app.core.TTS.adapter_registry import TTSAdapterRegistry, TTSProvider


def _make_wav_bytes(duration_seconds: float = 0.2, sample_rate: int = 16000) -> bytes:
    """Create a simple sine wave WAV payload for testing."""
    total_frames = int(duration_seconds * sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * total_frames)
    return buffer.getvalue()


@pytest.fixture
def adapter(tmp_path) -> IndexTTS2Adapter:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("model: dummy")
    model_dir = tmp_path / "checkpoints"
    model_dir.mkdir()

    adapter = IndexTTS2Adapter(
        {
            "index_tts_cfg_path": str(cfg_path),
            "index_tts_model_dir": str(model_dir),
        }
    )
    adapter._initialized = True
    adapter._status = ProviderStatus.AVAILABLE
    adapter._engine = MagicMock()
    return adapter


@pytest.mark.asyncio
async def test_generate_requires_voice_reference(adapter):
    request = TTSRequest(
        text="Hello world",
        voice="demo",
        format=AudioFormat.WAV,
        speed=1.0,
    )

    with pytest.raises(TTSValidationError):
        await adapter.generate(request)


@pytest.mark.asyncio
async def test_generate_basic_wav(adapter, monkeypatch):
    voice_bytes = _make_wav_bytes()
    emo_bytes = _make_wav_bytes(sample_rate=8000)

    infer_calls = []

    def fake_infer(spk_audio_prompt, text, output_path, **kwargs):
        infer_calls.append((spk_audio_prompt, text, output_path, kwargs))
        audio = np.ones((22050, 1), dtype=np.int16)
        return (22050, audio)

    adapter._engine.infer = fake_infer

    async def fake_convert_to_wav(input_path, output_path, sample_rate=24000, channels=1, bit_depth=16):
        data = Path(input_path).read_bytes()
        Path(output_path).write_bytes(data)
        return True

    async def fake_convert_format(input_path, output_path, target_format, **kwargs):
        target_file = Path(output_path).with_suffix(f".{target_format}")
        target_file.write_bytes(Path(input_path).read_bytes())
        return True

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.audio_converter.AudioConverter.convert_to_wav",
        fake_convert_to_wav,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.audio_converter.AudioConverter.convert_format",
        fake_convert_format,
    )

    request = TTSRequest(
        text="Test line",
        voice="demo",
        format=AudioFormat.MP3,
        speed=1.0,
        stream=False,
        voice_reference=voice_bytes,
        extra_params={
            "emo_audio_reference": base64.b64encode(emo_bytes).decode("ascii"),
            "emo_alpha": 0.7,
        },
    )

    response = await adapter.generate(request)

    assert response.audio_data and len(response.audio_data) > 0
    assert response.format == AudioFormat.MP3
    assert response.duration_seconds is not None
    assert response.duration_seconds > 0
    assert response.sample_rate == adapter.output_sample_rate

    assert infer_calls, "IndexTTS2 infer was not invoked"
    spk_path = infer_calls[0][0]
    emo_path = infer_calls[0][3]["emo_audio_prompt"]
    assert Path(spk_path).exists() is False
    if emo_path:
        assert Path(emo_path).exists() is False


@pytest.mark.asyncio
async def test_generate_unsupported_format(adapter):
    adapter._engine.infer = MagicMock(return_value=(22050, np.zeros((10, 1), dtype=np.int16)))

    request = TTSRequest(
        text="Hello",
        voice="demo",
        format=AudioFormat.FLAC,
        stream=False,
        voice_reference=_make_wav_bytes(),
    )

    with pytest.raises(TTSUnsupportedFormatError):
        await adapter.generate(request)


@pytest.mark.asyncio
async def test_generate_streaming_wav(adapter, monkeypatch):
    voice_bytes = _make_wav_bytes()

    chunks = [
        np.ones(512, dtype=np.float32) * 1000.0,
        np.zeros(256, dtype=np.float32),
    ]

    def fake_infer(*args, **kwargs):
        assert kwargs.get("stream_return") is True

        def iterator():
            for chunk in chunks:
                yield chunk

        return iterator()

    adapter._engine.infer = fake_infer

    class DummyWriter:
        def __init__(self, format: str, sample_rate: int, channels: int):
            self.format = format
            self.sample_rate = sample_rate
            self.channels = channels

        def write_chunk(self, audio_data=None, finalize: bool = False):
            if finalize:
                return b"EOF"
            if audio_data is None:
                return b""
            return audio_data.tobytes()

        def close(self):
            pass

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.adapters.index_tts_adapter.StreamingAudioWriter",
        DummyWriter,
    )

    request = TTSRequest(
        text="Stream request",
        voice="demo",
        format=AudioFormat.WAV,
        speed=1.0,
        voice_reference=voice_bytes,
        stream=True,
    )

    response = await adapter.generate(request)
    assert response.audio_stream is not None

    collected = bytearray()
    async for chunk in response.audio_stream:
        collected.extend(chunk)

    assert collected  # Should receive streamed bytes


def test_registry_includes_index_tts_provider():
    registry = TTSAdapterRegistry(config={"index_tts_enabled": False})
    assert TTSProvider.INDEX_TTS in registry._adapter_specs
