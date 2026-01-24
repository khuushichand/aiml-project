import asyncio
import json
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.api.v1.endpoints import audio
from tldw_Server_API.app.core.TTS.realtime_session import RealtimeSessionHandle, RealtimeTTSSession


class DummyWebSocket:
    def __init__(self, payloads):
        self.headers = {}
        self.query_params = {}
        self.client = SimpleNamespace(host="127.0.0.1")
        self._messages = [json.dumps(p) for p in payloads]
        self.sent_bytes = []
        self.sent_json = []
        self.accepted = False
        self.closed = False
        self.close_code = None

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if not self._messages:
            raise RuntimeError("No more messages")  # noqa: TRY003
        return self._messages.pop(0)

    async def send_bytes(self, data: bytes):
        self.sent_bytes.append(data)

    async def send_json(self, payload):
        self.sent_json.append(payload)

    async def close(self, code=1000, reason=None):  # noqa: ARG002
        self.closed = True
        self.close_code = code


class DummyRealtimeSession(RealtimeTTSSession):
    def __init__(self, chunks):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._chunks = chunks
        self._closed = False

    async def push_text(self, delta: str) -> None:  # noqa: ARG002
        return None

    async def commit(self) -> None:
        for chunk in self._chunks:
            await self._queue.put(chunk)

    async def finish(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._queue.put(None)

    async def audio_stream(self):
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item


class DummyRealtimeService:
    async def open_realtime_session(self, *_args, **_kwargs):
        session = DummyRealtimeSession([b"aa", b"bb"])
        return RealtimeSessionHandle(
            session=session,
            provider="vibevoice_realtime",
            warning="fallback to buffered session",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_realtime_streams_audio(monkeypatch: pytest.MonkeyPatch):
    payloads = [
        {"type": "config", "model": "vibevoice-realtime-0.5b", "format": "pcm"},
        {"type": "text", "delta": "hello"},
        {"type": "commit"},
        {"type": "final"},
    ]
    ws = DummyWebSocket(payloads)

    async def _auth_stub(*_args, **_kwargs):
        return True, 1

    async def _can_start_stream_stub(_user_id):
        return True, None

    async def _finish_stream_stub(_user_id):
        return None

    async def _get_tts_service_stub():
        return DummyRealtimeService()

    monkeypatch.setattr(audio, "_audio_ws_authenticate", _auth_stub)
    monkeypatch.setattr(audio, "can_start_stream", _can_start_stream_stub)
    monkeypatch.setattr(audio, "finish_stream", _finish_stream_stub)
    monkeypatch.setattr(audio, "get_tts_service", _get_tts_service_stub)

    await audio.websocket_tts_realtime(ws, token=None)

    assert ws.sent_bytes == [b"aa", b"bb"]
    assert any(msg.get("type") == "warning" for msg in ws.sent_json)
    assert any(msg.get("type") == "done" for msg in ws.sent_json)
    assert ws.closed is True
