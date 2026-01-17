import asyncio
import json
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.api.v1.endpoints import audio


class DummyWebSocket:
    def __init__(self, prompt_payload: dict):
        self.headers = {}
        self.query_params = {}
        self.client = SimpleNamespace(host="127.0.0.1")
        self._messages = [json.dumps(prompt_payload)]
        self.sent_bytes = []
        self.sent_json = []
        self.accepted = False
        self.closed = False
        self.close_code = None

    async def accept(self):
        # Allow idempotent accept
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


class _DummyTTSService:
    def __init__(self, chunks):
        self._chunks = chunks

    async def generate_speech(self, *_args, **_kwargs):  # noqa: ARG002
        for chunk in self._chunks:
            yield chunk


@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_streams_audio(monkeypatch: pytest.MonkeyPatch):
    prompt = {"type": "prompt", "text": "hello", "format": "pcm"}
    ws = DummyWebSocket(prompt)

    # Stub auth + quotas
    async def _auth_stub(*_args, **_kwargs):
        return True, 1

    async def _can_start_stream_stub(_user_id):
        return True, None

    async def _finish_stream_stub(_user_id):
        return None

    monkeypatch.setattr(audio, "_audio_ws_authenticate", _auth_stub)
    monkeypatch.setattr(audio, "can_start_stream", _can_start_stream_stub)
    monkeypatch.setattr(audio, "finish_stream", _finish_stream_stub)

    dummy_service = _DummyTTSService([b"abc", b"def"])

    async def _get_tts_service_stub():
        return dummy_service

    monkeypatch.setattr(audio, "get_tts_service", _get_tts_service_stub)

    # Run handler
    await audio.websocket_tts(ws, token=None)

    assert ws.sent_bytes == [b"abc", b"def"]
    # WebSocketStream.done sends a done frame before closing
    assert any(msg.get("type") == "done" for msg in ws.sent_json)
    assert ws.closed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_records_underrun(monkeypatch: pytest.MonkeyPatch):
    prompt = {"type": "prompt", "text": "hello", "format": "pcm"}
    ws = DummyWebSocket(prompt)

    class QueueStub:
        def __init__(self, *_args, **_kwargs):
            self.items = []
            self.first_full = True

        def put_nowait(self, item):

            if self.first_full:
                self.first_full = False
                raise asyncio.QueueFull
            self.items.append(item)

        async def put(self, item):
            self.items.append(item)

        async def get(self):
            while not self.items:
                await asyncio.sleep(0)
            return self.items.pop(0)

        def get_nowait(self):

            if not self.items:
                raise asyncio.QueueEmpty
            return self.items.pop(0)

    class DummyRegistry:
        def __init__(self):
            self.increments = []

        def increment(self, name, value=1, labels=None):

            self.increments.append((name, value, labels or {}))

        def observe(self, *_args, **_kwargs):  # noqa: ARG002
            return None

    reg = DummyRegistry()

    async def _auth_stub(*_args, **_kwargs):
        return True, 1

    async def _can_start_stream_stub(_user_id):
        return True, None

    async def _finish_stream_stub(_user_id):
        return None

    dummy_service = _DummyTTSService([b"a", b"b"])

    async def _get_tts_service_stub():
        return dummy_service

    monkeypatch.setattr(audio, "_audio_ws_authenticate", _auth_stub)
    monkeypatch.setattr(audio, "can_start_stream", _can_start_stream_stub)
    monkeypatch.setattr(audio, "finish_stream", _finish_stream_stub)
    monkeypatch.setattr(audio, "get_tts_service", _get_tts_service_stub)
    monkeypatch.setattr(audio, "get_metrics_registry", lambda: reg)
    monkeypatch.setattr(
        audio,
        "asyncio",
        SimpleNamespace(
            Queue=QueueStub,
            QueueFull=asyncio.QueueFull,
            QueueEmpty=asyncio.QueueEmpty,
            create_task=asyncio.create_task,
            wait=asyncio.wait,
            wait_for=asyncio.wait_for,
            FIRST_EXCEPTION=asyncio.FIRST_EXCEPTION,
            sleep=asyncio.sleep,
        ),
    )

    await audio.websocket_tts(ws, token=None)

    # First put_nowait raises, triggering underrun counter
    assert any(name == "audio_stream_underruns_total" for name, _, _ in reg.increments)
