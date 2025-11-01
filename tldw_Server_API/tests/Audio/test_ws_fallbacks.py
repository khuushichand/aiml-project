import asyncio
import json
from configparser import ConfigParser
import numpy as np
import pytest


class _DummyWebSocket:
    def __init__(self, frames):
        self._frames = list(frames)
        self.sent = []
        self.closed = False
        self.close_args = None

    async def receive_text(self):
        if not self._frames:
            # Simulate client gone
            await asyncio.sleep(0)
            raise asyncio.TimeoutError()
        return self._frames.pop(0)

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self, code: int | None = None, reason: str | None = None):
        self.closed = True
        self.close_args = (code, reason)


def _make_cfg(fallback: bool) -> ConfigParser:
    cfg = ConfigParser()
    cfg.add_section('STT-Settings')
    cfg.set('STT-Settings', 'streaming_fallback_to_whisper', 'true' if fallback else 'false')
    return cfg


class _FakeWhisperModel:
    class _Seg:
        def __init__(self, t: str):
            self.text = t

    class _Info:
        language = 'en'
        language_probability = 1.0

    def transcribe(self, path: str, **opts):
        # Return shape compatible with code: (segments, info)
        return [self._Seg("ok")], self._Info()


@pytest.mark.asyncio
async def test_model_unavailable_triggers_fallback_warning(monkeypatch):
    # Force Parakeet core variant builder to return None so adapter initialize fails
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.transcriber as core_tx
    monkeypatch.setattr(core_tx, "_variant_decode_fn", lambda m, v: None)

    # Enable fallback to Whisper
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified as unified
    monkeypatch.setattr(unified, "load_comprehensive_config", lambda: _make_cfg(True))
    monkeypatch.setattr(unified, "get_whisper_model", lambda size, device: _FakeWhisperModel())

    # Prepare websocket with config (parakeet-onnx) then stop
    cfg = json.dumps({"type": "config", "model": "parakeet-onnx", "sample_rate": 16000})
    stop = json.dumps({"type": "stop"})
    ws = _DummyWebSocket([cfg, stop])

    # Run handler
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        handle_unified_websocket, UnifiedStreamingConfig
    )

    await handle_unified_websocket(ws, UnifiedStreamingConfig())

    warnings = [m for m in ws.sent if m.get("type") == "warning"]
    assert warnings, "Expected at least one warning frame"
    # Look for fallback notice
    fallback_msgs = [w for w in warnings if w.get("fallback") is True]
    assert fallback_msgs, "Fallback to Whisper warning not emitted"


@pytest.mark.asyncio
async def test_model_unavailable_without_fallback_emits_error(monkeypatch):
    # Force Parakeet core variant builder to return None so adapter initialize fails
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.transcriber as core_tx
    monkeypatch.setattr(core_tx, "_variant_decode_fn", lambda m, v: None)

    # Disable fallback to Whisper
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified as unified
    monkeypatch.setattr(unified, "load_comprehensive_config", lambda: _make_cfg(False))

    cfg = json.dumps({"type": "config", "model": "parakeet-onnx", "sample_rate": 16000})
    stop = json.dumps({"type": "stop"})
    ws = _DummyWebSocket([cfg, stop])

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        handle_unified_websocket, UnifiedStreamingConfig
    )

    await handle_unified_websocket(ws, UnifiedStreamingConfig())

    errors = [m for m in ws.sent if m.get("type") == "error"]
    assert errors, "Expected an error frame when fallback disabled"
    assert any(e.get("error_type") == "model_unavailable" for e in errors)

