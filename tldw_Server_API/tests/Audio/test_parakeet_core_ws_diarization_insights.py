import asyncio
import base64
import json
import numpy as np
import pytest


class DummyWebSocket:
    def __init__(self, messages):
        self._messages = list(messages)
        self._out = []
        self.accepted = False
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if not self._messages:
            raise RuntimeError("No more messages")
        return self._messages.pop(0)

    async def send_json(self, data):
        self._out.append(data)

    async def close(self, code=None, reason=None):
        self.closed = True

    # Helpers
    @property
    def outputs(self):
        return self._out


@pytest.mark.asyncio
async def test_core_ws_with_diarization_and_insights(monkeypatch):
    # Import the core WS handler
    import tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.ws_server as wsmod

    # Patch in fake diarizer and insights classes if not available
    class _FakeSettings:
        def __init__(self, enabled=True):
            self.enabled = enabled

        @classmethod
        def from_client_payload(cls, payload):
            enabled = bool(payload.get("enabled", True))
            return cls(enabled=enabled)

    class _FakeInsights:
        def __init__(self, websocket, settings, **kwargs):
            self.websocket = websocket
            self.settings = settings
            self._seen = []

        def describe(self):
            return {"enabled": self.settings.enabled}

        async def on_transcript(self, segment):
            self._seen.append(segment)

        async def on_commit(self, full_text):
            self._seen.append({"commit": full_text})

        async def reset(self):
            self._seen.clear()

        async def close(self):
            pass

    class _FakeDiarizer:
        def __init__(self, sample_rate, store_audio=False, storage_dir=None, num_speakers=None):
            self.sample_rate = sample_rate
            self.map = {}

        async def ensure_ready(self):
            return True

        async def label_segment(self, audio_np, meta):
            seg_id = int(meta.get("segment_id", 0))
            info = {"speaker_id": 1, "speaker_label": "SPEAKER_TEST"}
            self.map[seg_id] = info
            return info

        async def finalize(self):
            return self.map, None, None

        async def reset(self):
            self.map.clear()

        async def close(self):
            pass

    monkeypatch.setattr(wsmod, "LiveInsightSettings", _FakeSettings, raising=False)
    monkeypatch.setattr(wsmod, "LiveMeetingInsights", _FakeInsights, raising=False)
    monkeypatch.setattr(wsmod, "StreamingDiarizer", _FakeDiarizer, raising=False)

    # Build messages: config (enable diarization/insights), audio, commit, stop
    cfg = {
        "type": "config",
        "model": "parakeet",
        "sample_rate": 10,
        "chunk_duration": 1.0,
        "enable_partial": False,
        "diarize": True,
        "insights": {"enabled": True},
    }
    audio = (np.ones(11, dtype=np.float32)).tobytes()  # 1.1s at 10 Hz
    messages = [
        json.dumps(cfg),
        json.dumps({"type": "audio", "data": base64.b64encode(audio).decode("ascii")}),
        json.dumps({"type": "commit"}),
        json.dumps({"type": "stop"}),
    ]
    ws = DummyWebSocket(messages)

    # Provide a simple decode function
    async def _run():
        def _decode(audio_np, sr):
            return "hello"

        await wsmod.websocket_parakeet_core(ws, decode_fn=_decode)

    await _run()

    outs = ws.outputs
    # Expect configuration status
    assert any(o.get("type") == "status" and o.get("state") == "configured" for o in outs)
    # Expect insights enabled status
    assert any(o.get("type") == "status" and o.get("state") in {"insights_enabled", "insights_disabled"} for o in outs)
    # Expect a final frame with speaker info
    finals = [o for o in outs if o.get("type") == "final"]
    assert finals, f"No final frames: {outs}"
    assert any("speaker_id" in f and "speaker_label" in f for f in finals)
    # Expect full transcript
    assert any(o.get("type") == "full_transcript" for o in outs)
    # Expect diarization summary
    assert any(o.get("type") == "diarization_summary" for o in outs)

