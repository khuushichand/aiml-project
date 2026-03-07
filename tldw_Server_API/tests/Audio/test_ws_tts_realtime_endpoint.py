import asyncio
import importlib.machinery
import json
import sys
from types import SimpleNamespace
import types
from typing import Any

import pytest

# Keep module imports deterministic in environments where torch-backed deps abort.
if "torch" not in sys.modules:
    _fake_torch = types.ModuleType("torch")
    _fake_torch.__spec__ = importlib.machinery.ModuleSpec("torch", loader=None)
    _fake_torch.Tensor = object
    _fake_torch.nn = SimpleNamespace(Module=object)
    sys.modules["torch"] = _fake_torch

if "faster_whisper" not in sys.modules:
    _fake_fw = types.ModuleType("faster_whisper")
    _fake_fw.__spec__ = importlib.machinery.ModuleSpec("faster_whisper", loader=None)

    class _StubWhisperModel:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
            return None

    _fake_fw.WhisperModel = _StubWhisperModel
    _fake_fw.BatchedInferencePipeline = _StubWhisperModel
    sys.modules["faster_whisper"] = _fake_fw

if "transformers" not in sys.modules:
    _fake_tf = types.ModuleType("transformers")
    _fake_tf.__spec__ = importlib.machinery.ModuleSpec("transformers", loader=None)

    class _StubProcessor:
        @classmethod
        def from_pretrained(cls, *args: Any, **kwargs: Any):  # noqa: ANN206, ARG002
            return cls()

    class _StubModel:
        @classmethod
        def from_pretrained(cls, *args: Any, **kwargs: Any):  # noqa: ANN206, ARG002
            return cls()

    _fake_tf.AutoProcessor = _StubProcessor
    _fake_tf.Qwen2AudioForConditionalGeneration = _StubModel
    sys.modules["transformers"] = _fake_tf

from tldw_Server_API.app.api.v1.endpoints import audio
from tldw_Server_API.app.core.TTS.realtime_session import RealtimeSessionHandle, RealtimeTTSSession


class DummyWebSocket:
    def __init__(self, payloads, *, headers=None, query_params=None):
        self.headers = dict(headers or {})
        self.query_params = dict(query_params or {})
        self.client = SimpleNamespace(host="127.0.0.1")
        self._messages = [json.dumps(p) for p in payloads]
        self.sent_bytes = []
        self.sent_json = []
        self.sent_events = []
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
        self.sent_events.append(("bytes", data))

    async def send_json(self, payload):
        self.sent_json.append(payload)
        self.sent_events.append(("json", dict(payload)))

    async def close(self, code=1000, reason=None):  # noqa: ARG002
        self.closed = True
        self.close_code = code


class DummyRealtimeSession(RealtimeTTSSession):
    def __init__(self, chunks):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._chunks = chunks
        self._closed = False
        self.finish_count = 0

    async def push_text(self, delta: str) -> None:  # noqa: ARG002
        return None

    async def commit(self) -> None:
        for chunk in self._chunks:
            await self._queue.put(chunk)

    async def finish(self) -> None:
        if self._closed:
            self.finish_count += 1
            return
        self._closed = True
        self.finish_count += 1
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_realtime_interrupt_cancels_without_close(monkeypatch: pytest.MonkeyPatch):
    payloads = [
        {"type": "config", "model": "vibevoice-realtime-0.5b", "format": "pcm"},
        {"type": "text", "delta": "hello"},
        {"type": "commit"},
        {"type": "interrupt", "reason": "barge_in"},
        {"type": "ping"},
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

    assert any(msg.get("type") == "interrupted" for msg in ws.sent_json)
    assert any(msg.get("type") == "pong" for msg in ws.sent_json)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_realtime_accepts_text_after_interrupt(monkeypatch: pytest.MonkeyPatch):
    payloads = [
        {"type": "config", "model": "vibevoice-realtime-0.5b", "format": "pcm"},
        {"type": "text", "delta": "hello"},
        {"type": "commit"},
        {"type": "interrupt", "reason": "barge_in"},
        {"type": "text", "delta": "after interrupt"},
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

    assert any(msg.get("type") == "interrupted" for msg in ws.sent_json)
    interrupted_idx = next(
        i for i, event in enumerate(ws.sent_events)
        if event[0] == "json" and event[1].get("type") == "interrupted"
    )
    bytes_after_interrupt = [
        event for event in ws.sent_events[interrupted_idx + 1:]
        if event[0] == "bytes"
    ]
    assert bytes_after_interrupt
    assert any(msg.get("type") == "done" for msg in ws.sent_json)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_realtime_error_frame_shape(monkeypatch: pytest.MonkeyPatch):
    request_id = "req-error-shape"
    payloads = [
        {"type": "config", "model": "vibevoice-realtime-0.5b", "format": "aac"},
    ]
    ws = DummyWebSocket(payloads, headers={"x-request-id": request_id})

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

    err = next((msg for msg in ws.sent_json if msg.get("type") == "error"), None)
    assert err is not None
    assert err.get("request_id") == request_id
    assert err.get("error_type") == "bad_request"
    assert ws.close_code == 4400


@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_realtime_provider_format_mismatch(monkeypatch: pytest.MonkeyPatch):
    request_id = "req-provider-mismatch"
    payloads = [
        {"type": "config", "model": "vibevoice-realtime-0.5b", "format": "flac"},
    ]
    ws = DummyWebSocket(payloads, headers={"x-request-id": request_id})
    session = DummyRealtimeSession([b"aa"])

    class MismatchRealtimeService:
        async def open_realtime_session(self, *_args, **_kwargs):
            return RealtimeSessionHandle(session=session, provider="elevenlabs")

    async def _auth_stub(*_args, **_kwargs):
        return True, 1

    async def _can_start_stream_stub(_user_id):
        return True, None

    async def _finish_stream_stub(_user_id):
        return None

    async def _get_tts_service_stub():
        return MismatchRealtimeService()

    monkeypatch.setattr(audio, "_audio_ws_authenticate", _auth_stub)
    monkeypatch.setattr(audio, "can_start_stream", _can_start_stream_stub)
    monkeypatch.setattr(audio, "finish_stream", _finish_stream_stub)
    monkeypatch.setattr(audio, "get_tts_service", _get_tts_service_stub)

    await audio.websocket_tts_realtime(ws, token=None)

    err = next((msg for msg in ws.sent_json if msg.get("type") == "error"), None)
    assert err is not None
    assert err.get("request_id") == request_id
    assert err.get("error_type") == "bad_request"
    assert ws.close_code == 4400
    assert session.finish_count >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_realtime_error_without_compat_alias(monkeypatch: pytest.MonkeyPatch):
    request_id = "req-no-compat-alias"
    payloads = [{"type": "config", "model": "vibevoice-realtime-0.5b", "format": "aac"}]
    ws = DummyWebSocket(payloads, headers={"x-request-id": request_id})

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
    monkeypatch.setenv("AUDIO_WS_COMPAT_ERROR_TYPE", "0")

    await audio.websocket_tts_realtime(ws, token=None)

    err = next((msg for msg in ws.sent_json if msg.get("type") == "error"), None)
    assert err is not None
    assert err.get("request_id") == request_id
    assert err.get("code") == "bad_request"
    assert err.get("error_type") is None
    assert ws.close_code == 4400
