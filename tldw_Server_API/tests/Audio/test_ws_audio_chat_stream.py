import asyncio
import base64
import json
import time
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.api.v1.endpoints import audio


class DummyWebSocket:
    def __init__(self, messages):
        self.headers = {}
        self.query_params = {}
        self.client = SimpleNamespace(host="127.0.0.1")
        self._messages = [json.dumps(m) if isinstance(m, dict) else m for m in messages]
        self.sent_bytes = []
        self.sent_json = []
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_calls = []

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if not self._messages:
            raise RuntimeError("No more messages")
        return self._messages.pop(0)

    async def send_bytes(self, data: bytes):
        self.sent_bytes.append(data)

    async def send_json(self, payload):
        self.sent_json.append(payload)

    async def close(self, code=1000, reason=None):  # noqa: ARG002
        self.close_calls.append(code)
        if not self.closed:
            self.close_code = code
        self.closed = True


class _DummyTranscriber:
    def __init__(self, config):  # noqa: ARG002
        self.reset_called = False

    def initialize(self):
        return None

    async def process_audio_chunk(self, audio_bytes):  # noqa: ARG002
        return {"type": "partial", "text": "hi"}

    def get_full_transcript(self):
        return "hello world"

    def reset(self):
        self.reset_called = True


class _DummyVAD:
    available = True
    unavailable_reason = None

    def __init__(self, *args, **kwargs):  # noqa: D401, ARG002
        self.last_trigger_at = time.time()

    def observe(self, audio_bytes):  # noqa: ARG002
        self.last_trigger_at = time.time()
        return False


class _DummyRegistry:
    def __init__(self):
        self.records = []
        self.registered = []

    def increment(self, name, value=1, labels=None):
        self.records.append(("inc", name, value, labels))

    def observe(self, name, value, labels=None):
        self.records.append(("obs", name, value, labels))

    def register_metric(self, *args, **kwargs):  # noqa: ARG002
        self.registered.append(args)


class _DummyTTSService:
    def __init__(self, chunks):
        self._chunks = chunks

    async def generate_speech(self, *args, **kwargs):  # noqa: ARG002
        for chunk in self._chunks:
            yield chunk


async def _llm_stub(**kwargs):  # noqa: ARG002
    async def _gen():
        yield 'data: {"choices":[{"delta":{"content":"hey "}}]}\n\n'
        yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        yield "data: [DONE]\n\n"

    return _gen()


@pytest.mark.asyncio
async def test_audio_chat_ws_streams_llm_and_tts(monkeypatch: pytest.MonkeyPatch):
    audio_payload = base64.b64encode(b"abc").decode("ascii")
    messages = [
        {
            "type": "config",
            "stt": {"model": "parakeet"},
            "llm": {"provider": "stub", "model": "stub-model"},
            "tts": {"voice": "af_heart", "format": "pcm"},
        },
        {"type": "audio", "data": audio_payload},
        {"type": "commit"},
        {"type": "stop"},
    ]
    ws = DummyWebSocket(messages)

    # Stubs
    async def _auth(*args, **kwargs):
        return True, 1

    monkeypatch.setattr(audio, "_audio_ws_authenticate", _auth)

    async def _can_start_stream(user_id):
        return True, None

    async def _finish_stream(user_id):
        return None

    async def _allow_minutes(uid, minutes):
        return True, None

    async def _add_minutes(uid, minutes):
        return None

    async def _hb(uid):
        return None

    monkeypatch.setattr(audio, "can_start_stream", _can_start_stream)
    monkeypatch.setattr(audio, "finish_stream", _finish_stream)
    monkeypatch.setattr(audio, "check_daily_minutes_allow", _allow_minutes)
    monkeypatch.setattr(audio, "add_daily_minutes", _add_minutes)
    monkeypatch.setattr(audio, "heartbeat_stream", _hb)

    monkeypatch.setattr(audio, "UnifiedStreamingTranscriber", _DummyTranscriber)
    monkeypatch.setattr(audio, "SileroTurnDetector", _DummyVAD)
    monkeypatch.setattr(audio, "chat_api_call_async", _llm_stub)
    monkeypatch.setattr(audio, "get_api_keys", lambda: {"stub": "fake"})

    async def _get_tts_service():
        return _DummyTTSService([b"tts1", b"tts2"])

    monkeypatch.setattr(audio, "get_tts_service", _get_tts_service)

    reg = _DummyRegistry()
    monkeypatch.setattr(audio, "get_metrics_registry", lambda: reg)

    await audio.websocket_audio_chat_stream(ws, token=None)

    # Assert LLM delta and transcript were sent
    assert any(msg.get("type") == "full_transcript" for msg in ws.sent_json)
    assert any(msg.get("type") == "llm_delta" for msg in ws.sent_json)
    assert any(msg.get("type") == "tts_done" for msg in ws.sent_json)
    assert ws.sent_bytes == [b"tts1", b"tts2"]
    assert ws.closed is True


@pytest.mark.asyncio
async def test_audio_chat_ws_quota_exceeded(monkeypatch: pytest.MonkeyPatch):
    audio_payload = base64.b64encode(b"abc").decode("ascii")
    ws = DummyWebSocket(
        [
            {"type": "config", "stt": {"model": "parakeet"}, "llm": {"model": "stub"}, "tts": {"format": "mp3"}},
            {"type": "audio", "data": audio_payload},
        ]
    )

    async def _auth(*args, **kwargs):
        return True, 1

    async def _can_start_stream(user_id):
        return True, None

    async def _finish_stream(user_id):
        return None

    async def _check_minutes(uid, minutes):
        return False, None

    async def _add_minutes(uid, minutes):
        return None

    monkeypatch.setattr(audio, "_audio_ws_authenticate", _auth)
    monkeypatch.setattr(audio, "can_start_stream", _can_start_stream)
    monkeypatch.setattr(audio, "finish_stream", _finish_stream)
    monkeypatch.setattr(audio, "check_daily_minutes_allow", _check_minutes)
    monkeypatch.setattr(audio, "add_daily_minutes", _add_minutes)
    monkeypatch.setattr(audio, "heartbeat_stream", lambda uid: None)
    monkeypatch.setattr(audio, "UnifiedStreamingTranscriber", _DummyTranscriber)
    monkeypatch.setattr(audio, "SileroTurnDetector", _DummyVAD)
    monkeypatch.setattr(audio, "chat_api_call_async", _llm_stub)
    monkeypatch.setattr(audio, "get_api_keys", lambda: {"stub": "fake"})
    monkeypatch.setattr(audio, "get_tts_service", lambda: _DummyTTSService([b"x"]))

    reg = _DummyRegistry()
    monkeypatch.setattr(audio, "get_metrics_registry", lambda: reg)

    await audio.websocket_audio_chat_stream(ws, token=None)

    quota_errors = [msg for msg in ws.sent_json if msg.get("error_type") == "quota_exceeded"]
    assert quota_errors, "Expected quota_exceeded message"
    # Close code should reflect quota policy (default 4003 unless env flips to 1008)
    assert ws.close_code in {4003, 1008}
    assert ws.closed is True


@pytest.mark.asyncio
async def test_audio_chat_ws_records_metrics(monkeypatch: pytest.MonkeyPatch):
    audio_payload = base64.b64encode(b"abcd").decode("ascii")
    ws = DummyWebSocket(
        [
            {
                "type": "config",
                "stt": {"model": "parakeet", "sample_rate": 16000},
                "llm": {"provider": "stub", "model": "stub-model"},
                "tts": {"voice": "af_heart", "format": "mp3"},
            },
            {"type": "audio", "data": audio_payload},
            {"type": "commit"},
            {"type": "stop"},
        ]
    )

    class QueueStub:
        def __init__(self, *args, **kwargs):  # noqa: ARG002
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

    class Registry:
        def __init__(self):
            self.increments = []
            self.observes = []
            self.registered = []

        def increment(self, name, value=1, labels=None):
            self.increments.append((name, value, labels or {}))

        def observe(self, name, value, labels=None):
            self.observes.append((name, value, labels or {}))

        def register_metric(self, *args, **kwargs):  # noqa: ARG002
            self.registered.append(args)

    reg = Registry()

    async def _auth(*args, **kwargs):
        return True, 1

    async def _can_start_stream(user_id):
        return True, None

    async def _finish_stream(user_id):
        return None

    async def _allow_minutes(uid, minutes):
        return True, 10.0

    async def _add_minutes(uid, minutes):
        return None

    async def _hb(uid):
        return None

    async def _get_tts_service():
        class _Service:
            async def generate_speech(self, *args, **kwargs):  # noqa: ARG002
                reg.observe(
                    "voice_to_voice_seconds",
                    0.5,
                    labels={"provider": "stub", "route": kwargs.get("voice_to_voice_route", "")},
                )
                yield b"a"
                yield b"b"

        return _Service()

    monkeypatch.setattr(audio, "_audio_ws_authenticate", _auth)
    monkeypatch.setattr(audio, "can_start_stream", _can_start_stream)
    monkeypatch.setattr(audio, "finish_stream", _finish_stream)
    monkeypatch.setattr(audio, "check_daily_minutes_allow", _allow_minutes)
    monkeypatch.setattr(audio, "add_daily_minutes", _add_minutes)
    monkeypatch.setattr(audio, "heartbeat_stream", _hb)
    monkeypatch.setattr(audio, "UnifiedStreamingTranscriber", _DummyTranscriber)
    monkeypatch.setattr(audio, "SileroTurnDetector", _DummyVAD)
    monkeypatch.setattr(audio, "chat_api_call_async", _llm_stub)
    monkeypatch.setattr(audio, "get_api_keys", lambda: {"stub": "fake"})
    monkeypatch.setattr(audio, "get_tts_service", _get_tts_service)
    monkeypatch.setattr(audio, "get_metrics_registry", lambda: reg)

    # Ensure WS helper uses the same registry
    import tldw_Server_API.app.core.Streaming.streams as streams

    monkeypatch.setattr(streams, "get_metrics_registry", lambda: reg)

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

    await audio.websocket_audio_chat_stream(ws, token=None)

    assert any(name == "audio_stream_underruns_total" for name, _, _ in reg.increments)
    assert any(name == "voice_to_voice_seconds" for name, _, _ in reg.observes)
    assert ws.closed is True
