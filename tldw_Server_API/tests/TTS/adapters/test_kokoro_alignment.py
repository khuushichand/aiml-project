import pytest
from unittest.mock import AsyncMock

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.kokoro_adapter import KokoroAdapter

pytestmark = pytest.mark.unit


class _Token:
    def __init__(self, text, start_ts, end_ts, *, whitespace=" ", segment_index=None):
        self.text = text
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.whitespace = whitespace
        if segment_index is not None:
            self._ = {"segment_index": segment_index}
        else:
            self._ = None


def test_build_alignment_payload_from_tokens():
    adapter = KokoroAdapter({"kokoro_use_onnx": False})
    tokens = [
        _Token("Hello", 0.0, 0.4),
        _Token("world", 0.45, 0.9),
    ]
    payload = adapter._build_alignment_payload(tokens, sample_rate=24000, text="Hello world")
    assert payload is not None
    assert payload["engine"] == "kokoro"
    assert payload["sample_rate"] == 24000
    assert payload["words"][0]["word"] == "Hello"
    assert payload["words"][0]["start_ms"] == 0
    assert payload["words"][0]["end_ms"] == 400
    assert payload["words"][0]["char_start"] == 0
    assert payload["words"][0]["char_end"] == 5
    assert payload["words"][1]["char_start"] == 6


def test_build_alignment_payload_handles_newlines():
    adapter = KokoroAdapter({"kokoro_use_onnx": False})
    tokens = [
        _Token("Hello", 0.0, 0.4, whitespace="\n"),
        _Token("world", 0.45, 0.9),
    ]
    payload = adapter._build_alignment_payload(tokens, sample_rate=24000, text="Hello\nworld")
    assert payload is not None
    assert payload["words"][0]["char_start"] == 0
    assert payload["words"][0]["char_end"] == 5
    assert payload["words"][1]["char_start"] == 6


def test_build_alignment_payload_respects_segment_index_offsets():
    adapter = KokoroAdapter({"kokoro_use_onnx": False})
    tokens = [
        _Token("world", 0.0, 0.4, segment_index=1, whitespace=""),
        _Token("Hello", 0.45, 0.9, segment_index=0, whitespace=""),
    ]
    payload = adapter._build_alignment_payload(tokens, sample_rate=24000, text="Hello\nworld")
    assert payload is not None
    assert payload["words"][0]["word"] == "world"
    assert payload["words"][0]["char_start"] == 6
    assert payload["words"][1]["word"] == "Hello"
    assert payload["words"][1]["char_start"] == 0


@pytest.mark.asyncio
async def test_generate_includes_alignment_metadata_for_pytorch(monkeypatch):
    adapter = KokoroAdapter({"kokoro_use_onnx": False})
    adapter.use_onnx = False
    adapter._deferred_model_load = False
    adapter.ensure_initialized = AsyncMock(return_value=True)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.adapters.kokoro_adapter.validate_tts_request",
        lambda *args, **kwargs: None,
    )
    adapter._process_voice = lambda voice: voice or "af_bella"
    adapter._get_language_from_voice = lambda voice: "en"
    adapter.preprocess_text = lambda text: text

    alignment_payload = {
        "engine": "kokoro",
        "sample_rate": 24000,
        "words": [{"word": "Hello", "start_ms": 0, "end_ms": 500}],
    }

    async def _fake_generate_with_alignment(*args, **kwargs):
        return b"audio", alignment_payload

    adapter._generate_complete_kokoro_with_alignment = _fake_generate_with_alignment

    request = TTSRequest(text="Hello", stream=False, format=AudioFormat.WAV)
    response = await adapter.generate(request)
    assert response.metadata.get("alignment") == alignment_payload
