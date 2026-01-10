import asyncio
import json
from configparser import ConfigParser
import numpy as np
import pytest


class _DummyWebSocket:
    def __init__(self, frames):
        """
        Construct a dummy WebSocket preloaded with incoming frames for tests.

        Parameters:
            frames (iterable): An iterable of frames (typically strings) that will be copied into an internal queue and returned one-by-one by receive_text().
        """
        self._frames = list(frames)
        self.sent = []
        self.closed = False
        self.close_args = None

    async def receive_text(self):
        """
        Return the next queued text frame from the mock WebSocket.

        If no frames remain, simulates a client timeout by raising asyncio.TimeoutError.

        Returns:
            str: The next text frame.

        Raises:
            asyncio.TimeoutError: When there are no queued frames to deliver.
        """
        if not self._frames:
            # Simulate client gone
            await asyncio.sleep(0)
            raise asyncio.TimeoutError()
        return self._frames.pop(0)

    async def send_json(self, payload):
        """
        Record an outgoing JSON payload for the mock WebSocket.

        Parameters:
            payload: The JSON-serializable object to record; appended to the mock's `sent` list.
        """
        self.sent.append(payload)

    async def close(self, code: int | None = None, reason: str | None = None):
        """
        Mark the websocket as closed and record the close code and reason.

        Parameters:
            code (int | None): Optional numeric close code.
            reason (str | None): Optional human-readable reason for the close.
        """
        self.closed = True
        self.close_args = (code, reason)


def _make_cfg(fallback: bool) -> ConfigParser:
    """
    Create a ConfigParser with the "STT-Settings" section and the streaming_fallback_to_whisper flag.

    Parameters:
        fallback (bool): If True, sets "streaming_fallback_to_whisper" to 'true'; otherwise sets it to 'false'.

    Returns:
        ConfigParser: A parser containing the "STT-Settings" section with the configured "streaming_fallback_to_whisper" value.
    """
    cfg = ConfigParser()
    cfg.add_section('STT-Settings')
    cfg.set('STT-Settings', 'streaming_fallback_to_whisper', 'true' if fallback else 'false')
    return cfg


class _FakeWhisperModel:
    class _Seg:
        def __init__(self, t: str):
            """
            Initialize the segment with its transcribed text.

            Parameters:
                t (str): The transcribed text to store on the segment as `text`.
            """
            self.text = t

    class _Info:
        language = 'en'
        language_probability = 1.0

    def transcribe(self, path: str, **opts):
        # Return shape compatible with code: (segments, info)
        """
        Provide a minimal, test-only transcription result compatible with the expected (segments, info) shape.

        Parameters:
            path (str): Path to the audio file to transcribe (ignored by this fake implementation).
            **opts: Additional transcription options accepted for API compatibility (ignored).

        Returns:
            tuple: A pair (segments, info) where `segments` is a list containing a single object with a `text` attribute equal to `"ok"`, and `info` is an object with `language` set to `'en'` and `language_probability` set to `1.0`.
        """
        return [self._Seg("ok")], self._Info()


@pytest.mark.asyncio
async def test_model_unavailable_triggers_fallback_warning(monkeypatch):
    # Force Parakeet core variant builder to return None so adapter initialize fails
    """
    Verify that when the primary transcription model is unavailable and fallback to Whisper is enabled, the websocket handler emits at least one warning frame indicating a fallback.

    Sets up the environment so the primary model initialization fails, enables Whisper fallback, provides a fake Whisper model, and sends a config then stop frame to the handler; asserts that at least one sent message has type "warning" and that a warning with "fallback" == True is present.
    """
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
    """
    Verify that when the primary transcription model is unavailable and Whisper fallback is disabled, the websocket handler emits an error frame indicating `model_unavailable`.

    This test patches the core variant decoder to force adapter initialization failure, disables streaming fallback to Whisper, sends a config and stop message via a dummy websocket, runs the unified websocket handler, and asserts that at least one sent frame has `"type": "error"` and an `"error_type"` equal to `"model_unavailable"`.
    """
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
