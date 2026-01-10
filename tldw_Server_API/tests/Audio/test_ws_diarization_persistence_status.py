import asyncio
import json
import pytest


class _DummyWebSocket:
    def __init__(self, frames):
             self._frames = list(frames)
        self.sent = []
        self.closed = False

    async def receive_text(self):
        if not self._frames:
            await asyncio.sleep(0)
            raise asyncio.TimeoutError()
        return self._frames.pop(0)

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self, code: int | None = None, reason: str | None = None):
        self.closed = True


class _FakeWhisperModel:
    class _Seg:
        def __init__(self, t: str):
            self.text = t

    class _Info:
        language = 'en'
        language_probability = 1.0

    def transcribe(self, path: str, **opts):
        return [self._Seg("ok")], self._Info()


@pytest.mark.asyncio
async def test_status_emitted_when_persistence_degraded(monkeypatch):
    # Use Whisper for easy model init
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified as unified

    monkeypatch.setattr(unified, "get_whisper_model", lambda size, device: _FakeWhisperModel())

    class _FakeDiarizer:
        def __init__(self, *args, **kwargs):
                     self.persistence_method = "wave"  # simulate non-soundfile fallback

        async def ensure_ready(self):
            return True

        async def label_segment(self, *args, **kwargs):
            return None

        async def finalize(self):
            return {}, "/tmp/fake.wav", []

        async def reset(self):
            pass

        async def close(self):
            pass

    monkeypatch.setattr(unified, "StreamingDiarizer", _FakeDiarizer, raising=False)

    cfg = json.dumps({
        "type": "config",
        "model": "whisper",
        "diarization_enabled": True,
        "diarization_store_audio": True,
    })
    commit = json.dumps({"type": "commit"})
    stop = json.dumps({"type": "stop"})
    ws = _DummyWebSocket([cfg, commit, stop])

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        handle_unified_websocket, UnifiedStreamingConfig
    )

    await handle_unified_websocket(ws, UnifiedStreamingConfig())

    # Expect a status frame indicating persistence degraded
    statuses = [m for m in ws.sent if m.get("type") == "status" and m.get("state") == "diarization_persist_degraded"]
    assert statuses, f"Expected diarization_persist_degraded status, got: {ws.sent}"


@pytest.mark.asyncio
async def test_status_emitted_when_persistence_disabled(monkeypatch):
    # Use Whisper for easy model init
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified as unified

    monkeypatch.setattr(unified, "get_whisper_model", lambda size, device: _FakeWhisperModel())

    class _FakeDiarizer2:
        def __init__(self, *args, **kwargs):
                     self.persistence_method = None  # simulate disabled

        async def ensure_ready(self):
            return True

        async def label_segment(self, *args, **kwargs):
            return None

        async def finalize(self):
            return {}, None, []

        async def reset(self):
            pass

        async def close(self):
            pass

    monkeypatch.setattr(unified, "StreamingDiarizer", _FakeDiarizer2, raising=False)

    cfg = json.dumps({
        "type": "config",
        "model": "whisper",
        "diarization_enabled": True,
        "diarization_store_audio": True,
    })
    commit = json.dumps({"type": "commit"})
    stop = json.dumps({"type": "stop"})
    ws = _DummyWebSocket([cfg, commit, stop])

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        handle_unified_websocket, UnifiedStreamingConfig
    )

    await handle_unified_websocket(ws, UnifiedStreamingConfig())

    # Expect a warning and a disabled status
    warnings = [m for m in ws.sent if m.get("type") == "warning" and m.get("warning_type") == "audio_persistence_unavailable"]
    assert warnings, f"Expected audio_persistence_unavailable warning, got: {ws.sent}"
    statuses = [m for m in ws.sent if m.get("type") == "status" and m.get("state") == "diarization_persist_disabled"]
    assert statuses, f"Expected diarization_persist_disabled status, got: {ws.sent}"
